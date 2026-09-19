"use client";

import { useState } from "react";

function toHex(value: DataView) {
  return Array.from(new Uint8Array(value.buffer, value.byteOffset, value.byteLength))
    .map(byte => byte.toString(16).padStart(2, "0"))
    .join("");
}

export default function DeviceLab() {
  const [serviceUuid, setServiceUuid] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [result, setResult] = useState<unknown>(null);

  async function connectBluetooth() {
    try {
      if (!authorized) throw new Error("Confirm that you own or are authorized to use the device first.");
      const bluetooth = (navigator as any).bluetooth;
      if (!bluetooth) throw new Error("Web Bluetooth is not available in this browser.");

      const requestedService = serviceUuid.trim();
      const options: any = { acceptAllDevices: true };
      if (requestedService) options.optionalServices = [requestedService];

      const device = await bluetooth.requestDevice(options);
      const details: any = {
        name: device.name || null,
        id: device.id,
        gatt_available: Boolean(device.gatt),
        connected: false,
        requested_service: requestedService || null,
      };

      if (device.gatt) {
        const server = await device.gatt.connect();
        details.connected = Boolean(server.connected);

        if (requestedService) {
          const service = await server.getPrimaryService(requestedService);
          const characteristics = await service.getCharacteristics();
          details.service = {
            uuid: service.uuid,
            characteristics: [],
          };

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
        }
      }

      setResult(details);
    } catch (error: any) {
      setResult(`Bluetooth: ${error.message}`);
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
      <p>Uses browser permission APIs for a device you own or control. Bluetooth can connect to the device you choose and, when you provide an allowed GATT service UUID, enumerate and read readable characteristics.</p>
      <label>Optional Bluetooth GATT service UUID</label>
      <input value={serviceUuid} onChange={event => setServiceUuid(event.target.value)} placeholder="e.g. battery_service or 0000180f-0000-1000-8000-00805f9b34fb" />
      <div className="check">
        <input type="checkbox" checked={authorized} onChange={event => setAuthorized(event.target.checked)} />
        <span>I own or am explicitly authorized to interact with the selected device/tag.</span>
      </div>
      <div className="actions">
        <button onClick={connectBluetooth} disabled={!authorized}>Choose + connect Bluetooth</button>
        <button className="secondary" onClick={readNfc} disabled={!authorized}>Read NFC tag</button>
        <button className="secondary" onClick={connectionInfo}>Connection info</button>
      </div>
      {result !== null && <pre className="output">{typeof result === "string" ? result : JSON.stringify(result, null, 2)}</pre>}
    </section>
  );
}
