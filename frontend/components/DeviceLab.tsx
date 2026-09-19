"use client";

import { useRef, useState } from "react";

function toHex(value: DataView) {
  return Array.from(new Uint8Array(value.buffer, value.byteOffset, value.byteLength))
    .map(byte => byte.toString(16).padStart(2, "0"))
    .join("");
}

function parseHex(value: string) {
  const clean = value.replace(/[^0-9a-f]/gi, "");
  if (!clean || clean.length % 2 !== 0) throw new Error("Enter an even number of hexadecimal characters.");
  if (clean.length > 128) throw new Error("Keep a single Bluetooth write to 64 bytes or less.");
  return Uint8Array.from(clean.match(/.{2}/g) || [], byte => Number.parseInt(byte, 16));
}

export default function DeviceLab() {
  const [serviceUuid, setServiceUuid] = useState("");
  const [characteristicUuid, setCharacteristicUuid] = useState("");
  const [writeHex, setWriteHex] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [result, setResult] = useState<unknown>(null);
  const characteristicRef = useRef<any>(null);

  async function connectBluetooth() {
    try {
      if (!authorized) throw new Error("Confirm that you own or are authorized to use the device first.");
      const bluetooth = (navigator as any).bluetooth;
      if (!bluetooth) throw new Error("Web Bluetooth is not available in this browser.");

      const requestedService = serviceUuid.trim();
      const requestedCharacteristic = characteristicUuid.trim();
      const options: any = { acceptAllDevices: true };
      if (requestedService) options.optionalServices = [requestedService];

      const device = await bluetooth.requestDevice(options);
      characteristicRef.current = null;
      const details: any = {
        name: device.name || null,
        id: device.id,
        gatt_available: Boolean(device.gatt),
        connected: false,
        requested_service: requestedService || null,
        requested_characteristic: requestedCharacteristic || null,
      };

      if (device.gatt) {
        const server = await device.gatt.connect();
        details.connected = Boolean(server.connected);

        if (requestedService) {
          const service = await server.getPrimaryService(requestedService);
          const characteristics = await service.getCharacteristics();
          details.service = { uuid: service.uuid, characteristics: [] };

          for (const characteristic of characteristics) {
            const entry: any = {
              uuid: characteristic.uuid,
              properties: {
                read: Boolean(characteristic.properties?.read),
                write: Boolean(characteristic.properties?.write),
                writeWithoutResponse: Boolean(characteristic.properties?.writeWithoutResponse),
                notify: Boolean(characteristic.properties?.notify),
                indicate: Boolean(characteristic.properties?.indicate),
              },
            };
            if (characteristic.properties?.read) {
              try {
                const value = await characteristic.readValue();
                entry.value_hex = toHex(value);
              } catch (error: any) {
                entry.read_error = error?.message || "Read failed";
              }
            }
            details.service.characteristics.push(entry);
          }

          if (requestedCharacteristic) {
            const selected = await service.getCharacteristic(requestedCharacteristic);
            characteristicRef.current = selected;
            details.selected_characteristic = {
              uuid: selected.uuid,
              read: Boolean(selected.properties?.read),
              write: Boolean(selected.properties?.write),
              writeWithoutResponse: Boolean(selected.properties?.writeWithoutResponse),
            };
          }
        }
      }

      setResult(details);
    } catch (error: any) {
      characteristicRef.current = null;
      setResult(`Bluetooth: ${error.message}`);
    }
  }

  async function writeBluetooth() {
    try {
      if (!authorized) throw new Error("Authorization confirmation is required.");
      const characteristic = characteristicRef.current;
      if (!characteristic) throw new Error("Connect to a Bluetooth service and characteristic first.");
      const bytes = parseHex(writeHex);
      if (characteristic.properties?.writeWithoutResponse && characteristic.writeValueWithoutResponse) {
        await characteristic.writeValueWithoutResponse(bytes);
      } else if (characteristic.properties?.write && characteristic.writeValueWithResponse) {
        await characteristic.writeValueWithResponse(bytes);
      } else if (characteristic.writeValue) {
        await characteristic.writeValue(bytes);
      } else {
        throw new Error("The selected characteristic is not writable.");
      }
      setResult({ status: "written", characteristic: characteristic.uuid, bytes: bytes.length, hex: writeHex });
    } catch (error: any) {
      setResult(`Bluetooth write: ${error.message}`);
    }
  }

  async function chooseHid() {
    try {
      if (!authorized) throw new Error("Authorization confirmation is required.");
      const hid = (navigator as any).hid;
      if (!hid) throw new Error("WebHID is not available in this browser.");
      const devices = await hid.requestDevice({ filters: [] });
      const device = devices?.[0];
      if (!device) throw new Error("No HID device selected.");
      if (!device.opened) await device.open();
      setResult({
        type: "hid",
        productName: device.productName || null,
        vendorId: device.vendorId,
        productId: device.productId,
        opened: Boolean(device.opened),
        collections: (device.collections || []).map((collection: any) => ({ usagePage: collection.usagePage, usage: collection.usage })),
        note: "Connected through the browser permission prompt. No reports are sent automatically.",
      });
    } catch (error: any) {
      setResult(`HID: ${error.message}`);
    }
  }

  async function chooseUsb() {
    try {
      if (!authorized) throw new Error("Authorization confirmation is required.");
      const usb = (navigator as any).usb;
      if (!usb) throw new Error("WebUSB is not available in this browser.");
      const device = await usb.requestDevice({ filters: [] });
      setResult({
        type: "usb",
        productName: device.productName || null,
        manufacturerName: device.manufacturerName || null,
        serialNumber: device.serialNumber || null,
        vendorId: device.vendorId,
        productId: device.productId,
        note: "Device selected with browser permission. WatchDog does not claim interfaces or send USB commands automatically.",
      });
    } catch (error: any) {
      setResult(`USB: ${error.message}`);
    }
  }

  async function readNfc() {
    try {
      if (!authorized) throw new Error("Confirm that you own or are authorized to use the tag first.");
      const Reader = (window as any).NDEFReader;
      if (!Reader) throw new Error("Web NFC is not available in this browser.");
      const reader = new Reader();
      await reader.scan();
      setResult("NFC scanner armed. Hold an NDEF-compatible tag near the phone.");
      reader.onreading = (event: any) => {
        setResult({
          serialNumber: event.serialNumber || null,
          records: event.message?.records?.map((record: any) => ({
            recordType: record.recordType,
            mediaType: record.mediaType || null,
            encoding: record.encoding || null,
            lang: record.lang || null,
          })) || [],
        });
      };
    } catch (error: any) {
      setResult(`NFC: ${error.message}`);
    }
  }

  function connectionInfo() {
    const connection = (navigator as any).connection || (navigator as any).mozConnection || (navigator as any).webkitConnection;
    if (!connection) {
      setResult("The browser does not expose the Network Information API on this device.");
      return;
    }
    setResult({
      type: connection.type || null,
      effectiveType: connection.effectiveType || null,
      downlinkMbps: connection.downlink ?? null,
      rttMs: connection.rtt ?? null,
      saveData: Boolean(connection.saveData),
      note: "Browser connection telemetry only. Browsers do not expose nearby Wi-Fi passwords or a general Wi-Fi backdoor.",
    });
  }

  return (
    <section className="card">
      <h2>Authorized Device Lab</h2>
      <p>Permission-gated controls for devices you own or are explicitly allowed to repair or operate. Web Bluetooth can inspect a selected GATT service and send a value to a writable characteristic; HID, USB and NFC use the browser's own device picker.</p>

      <label>Bluetooth GATT service UUID</label>
      <input value={serviceUuid} onChange={event => setServiceUuid(event.target.value)} placeholder="e.g. battery_service or 0000180f-0000-1000-8000-00805f9b34fb" />
      <label>Optional writable characteristic UUID</label>
      <input value={characteristicUuid} onChange={event => setCharacteristicUuid(event.target.value)} placeholder="Characteristic UUID supplied by the device documentation" />
      <label>Hex payload for the selected writable characteristic</label>
      <input value={writeHex} onChange={event => setWriteHex(event.target.value)} placeholder="Example: 01ff00" />

      <div className="check">
        <input type="checkbox" checked={authorized} onChange={event => setAuthorized(event.target.checked)} />
        <span>I own or am explicitly authorized to interact with the selected device/tag.</span>
      </div>
      <div className="actions">
        <button onClick={connectBluetooth} disabled={!authorized}>Choose + connect Bluetooth</button>
        <button className="secondary" onClick={writeBluetooth} disabled={!authorized || !writeHex.trim()}>Send Bluetooth value</button>
        <button className="secondary" onClick={chooseHid} disabled={!authorized}>Choose HID device</button>
        <button className="secondary" onClick={chooseUsb} disabled={!authorized}>Choose USB device</button>
        <button className="secondary" onClick={readNfc} disabled={!authorized}>Read NFC tag</button>
        <button className="secondary" onClick={connectionInfo}>Connection info</button>
      </div>
      <div className="banner" style={{ marginTop: 12 }}>For TVs, computers and other network devices, WatchDog should use the device's documented pairing/control protocol rather than guessing passwords or bypassing access controls. Browser support varies by phone and device.</div>
      {result !== null && <pre className="output">{typeof result === "string" ? result : JSON.stringify(result, null, 2)}</pre>}
    </section>
  );
}
