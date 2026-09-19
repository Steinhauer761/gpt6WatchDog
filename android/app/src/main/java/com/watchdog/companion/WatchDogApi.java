package com.watchdog.companion;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

final class WatchDogApi {
    private static final int CONNECT_TIMEOUT_MS = 7000;
    private static final int READ_TIMEOUT_MS = 9000;

    static final class PairResult {
        final String apiUrl;
        final String token;
        final long expiresAt;

        PairResult(String apiUrl, String token, long expiresAt) {
            this.apiUrl = apiUrl;
            this.token = token;
            this.expiresAt = expiresAt;
        }
    }

    PairResult pair(String rawApiUrl, String password, String deviceName) throws Exception {
        String apiUrl = normalizeApiUrl(rawApiUrl);
        JSONObject loginBody = new JSONObject().put("password", password);
        JSONObject login = post(apiUrl + "/v1/auth/login", null, loginBody);
        String adminToken = login.getString("token");

        JSONObject pairBody = new JSONObject().put("device_name", deviceName);
        JSONObject paired = post(apiUrl + "/v1/mobile/pair", adminToken, pairBody);
        return new PairResult(apiUrl, paired.getString("token"), paired.getLong("expires_at"));
    }

    JSONObject triageText(String apiUrl, String token, String text) throws Exception {
        return post(apiUrl + "/v1/mobile/triage/text", token, new JSONObject().put("text", text));
    }

    JSONObject triageScam(String apiUrl, String token, String number, String channel, String message) throws Exception {
        JSONObject body = new JSONObject()
                .put("number", number == null ? "" : number)
                .put("channel", channel == null ? "sms" : channel)
                .put("message", message == null ? "" : message)
                .put("unsolicited", true)
                .put("repeat_count", 1);
        return post(apiUrl + "/v1/mobile/scam/triage", token, body);
    }

    private JSONObject post(String url, String token, JSONObject body) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("Accept", "application/json");
        if (token != null && !token.isEmpty()) {
            connection.setRequestProperty("Authorization", "Bearer " + token);
        }

        byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(payload.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(payload);
        }

        int status = connection.getResponseCode();
        InputStream stream = status >= 200 && status < 300 ? connection.getInputStream() : connection.getErrorStream();
        String text = readAll(stream);
        JSONObject parsed = text.isEmpty() ? new JSONObject() : new JSONObject(text);
        if (status < 200 || status >= 300) {
            String detail = parsed.optString("detail", "HTTP " + status);
            throw new IllegalStateException(detail);
        }
        return parsed;
    }

    private static String readAll(InputStream stream) throws Exception {
        if (stream == null) return "";
        StringBuilder result = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) result.append(line);
        }
        return result.toString();
    }

    private static String normalizeApiUrl(String raw) {
        String value = raw == null ? "" : raw.trim();
        while (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        if (!value.startsWith("https://")) {
            throw new IllegalArgumentException("Use the HTTPS address of your WatchDog backend.");
        }
        return value;
    }
}
