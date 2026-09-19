package com.watchdog.companion;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.role.RoleManager;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int CALL_SCREENING_REQUEST = 4102;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private WatchDogApi api;
    private SecureStore secureStore;
    private LocalBlockStore blockStore;

    private EditText apiField;
    private EditText passwordField;
    private EditText deviceField;
    private EditText numberField;
    private EditText scanField;
    private TextView connectionStatus;
    private TextView protectionStatus;
    private TextView resultView;
    private Switch autoBlockSwitch;
    private JSONObject lastTechnical;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        api = new WatchDogApi();
        secureStore = new SecureStore(this);
        blockStore = new LocalBlockStore(this);
        getWindow().setStatusBarColor(Color.rgb(7, 9, 13));
        getWindow().setNavigationBarColor(Color.rgb(7, 9, 13));
        buildUi();
        loadSavedConnection();
        refreshProtectionStatus();
        handleIncomingIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIncomingIntent(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshProtectionStatus();
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(7, 9, 13));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(22), dp(18), dp(32));
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = text("WatchDog Companion", 28, Color.WHITE, true);
        root.addView(title);
        TextView subtitle = text(
                "Advanced protection with simple explanations. Share something to WatchDog, scan it, and keep high-risk phone numbers blocked locally.",
                15,
                Color.rgb(175, 193, 201),
                false);
        subtitle.setPadding(0, dp(6), 0, dp(18));
        root.addView(subtitle);

        LinearLayout connection = card();
        connection.addView(sectionTitle("1. Connect to your WatchDog backend"));
        connection.addView(sectionDescription(
                "Enter the HTTPS address of your Python backend and your console password once. The password is used only to pair this phone; the app stores a limited mobile token encrypted by Android Keystore."));
        apiField = field("https://your-watchdog-api.example", false, false);
        passwordField = field("WatchDog console password", true, false);
        deviceField = field("This phone", false, false);
        connection.addView(apiField);
        connection.addView(passwordField);
        connection.addView(deviceField);
        connection.addView(button("Connect + pair phone", v -> connectPhone(), false));
        connectionStatus = sectionDescription("Not connected yet.");
        connection.addView(connectionStatus);
        root.addView(connection, cardParams());

        LinearLayout protection = card();
        protection.addView(sectionTitle("2. Phone protection"));
        protection.addView(sectionDescription(
                "WatchDog can become Android's call-screening app. Numbers that WatchDog has already scored 8–10 can be saved to a local block list and rejected before they ring. This does not block IP addresses and does not affect web, Tor, or research searches."));
        protection.addView(button("Enable Android call screening", v -> requestCallScreeningRole(), false));
        autoBlockSwitch = new Switch(this);
        autoBlockSwitch.setText("Auto-block phone numbers scored 8–10");
        autoBlockSwitch.setTextColor(Color.WHITE);
        autoBlockSwitch.setTextSize(15);
        autoBlockSwitch.setChecked(blockStore.isAutoBlockEnabled());
        autoBlockSwitch.setPadding(0, dp(10), 0, dp(8));
        autoBlockSwitch.setOnCheckedChangeListener((buttonView, checked) -> blockStore.setAutoBlockEnabled(checked));
        protection.addView(autoBlockSwitch);
        protectionStatus = sectionDescription("");
        protection.addView(protectionStatus);
        protection.addView(button("Review blocked numbers", v -> showBlockedNumbers(), true));
        root.addView(protection, cardParams());

        LinearLayout scan = card();
        scan.addView(sectionTitle("3. Scan something"));
        scan.addView(sectionDescription(
                "Paste text here, or use Share → WatchDog from Messages, a browser, or a social app. You can also select text and choose WatchDog. If you include a phone number, the scam checker gives the incident a 1–10 score."));
        numberField = field("Phone number (optional)", false, false);
        scanField = field("Message, post, link, email header, or other text to inspect", false, true);
        scan.addView(numberField);
        scan.addView(scanField);
        LinearLayout scanButtons = new LinearLayout(this);
        scanButtons.setOrientation(LinearLayout.HORIZONTAL);
        Button scanButton = button("Scan now", v -> scanNow(), false);
        Button unblockButton = button("Unblock number", v -> unblockCurrentNumber(), true);
        scanButtons.addView(scanButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        LinearLayout.LayoutParams unblockParams = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        unblockParams.setMargins(dp(8), 0, 0, 0);
        scanButtons.addView(unblockButton, unblockParams);
        scan.addView(scanButtons);
        resultView = sectionDescription("Results will appear here in plain language.");
        resultView.setTextColor(Color.rgb(220, 229, 233));
        scan.addView(resultView);
        scan.addView(button("Technical details", v -> showTechnicalDetails(), true));
        root.addView(scan, cardParams());

        LinearLayout privacy = card();
        privacy.addView(sectionTitle("How Android scanning works"));
        privacy.addView(sectionDescription(
                "Incoming call blocking is automatic after you grant the Call Screening role. For texts and social posts, WatchDog scans only what you explicitly Share or select for WatchDog. It does not request broad SMS history or hidden background access."));
        root.addView(privacy, cardParams());

        setContentView(scroll);
    }

    private void connectPhone() {
        final String apiUrl = apiField.getText().toString().trim();
        final String password = passwordField.getText().toString();
        final String deviceName = deviceField.getText().toString().trim().isEmpty()
                ? "Android companion"
                : deviceField.getText().toString().trim();

        if (apiUrl.isEmpty() || password.isEmpty()) {
            connectionStatus.setText("Enter the backend HTTPS address and console password first.");
            return;
        }

        connectionStatus.setText("Pairing this phone…");
        executor.submit(() -> {
            try {
                WatchDogApi.PairResult result = api.pair(apiUrl, password, deviceName);
                secureStore.putString("api_url", result.apiUrl);
                secureStore.putString("mobile_token", result.token);
                secureStore.putString("mobile_expires", Long.toString(result.expiresAt));
                runOnUiThread(() -> {
                    passwordField.setText("");
                    connectionStatus.setText("Connected. This phone has a limited WatchDog mobile token stored with Android Keystore.");
                });
            } catch (Exception error) {
                runOnUiThread(() -> connectionStatus.setText("Could not connect: " + safeMessage(error)));
            }
        });
    }

    private void scanNow() {
        final String apiUrl = secureStore.getString("api_url");
        final String token = secureStore.getString("mobile_token");
        final String number = numberField.getText().toString().trim();
        final String text = scanField.getText().toString().trim();

        if (apiUrl == null || token == null) {
            resultView.setText("Connect this phone to the WatchDog backend first.");
            return;
        }
        if (text.isEmpty() && number.isEmpty()) {
            resultView.setText("Paste or share something to scan first.");
            return;
        }

        resultView.setText("Scanning through the WatchDog Python backend…");
        executor.submit(() -> {
            try {
                JSONObject result = number.isEmpty()
                        ? api.triageText(apiUrl, token, text)
                        : api.triageScam(apiUrl, token, number, "sms", text);
                runOnUiThread(() -> showScanResult(result, number));
            } catch (Exception error) {
                runOnUiThread(() -> resultView.setText("Scan failed: " + safeMessage(error)));
            }
        });
    }

    private void showScanResult(JSONObject result, String number) {
        lastTechnical = result;
        if (result.has("score")) {
            int score = result.optInt("score", 1);
            String disposition = result.optString("disposition", "unknown").replace('_', ' ');
            String summary = result.optString("summary", "No summary was returned.");
            StringBuilder plain = new StringBuilder();
            plain.append("Score: ").append(score).append("/10 — ").append(disposition.toUpperCase()).append("\n\n");
            plain.append(summary);

            JSONArray factors = result.optJSONArray("factors");
            if (factors != null && factors.length() > 0) {
                plain.append("\n\nWhy:\n");
                for (int i = 0; i < Math.min(factors.length(), 5); i++) {
                    JSONObject factor = factors.optJSONObject(i);
                    if (factor != null) plain.append("• ").append(factor.optString("reason", "Indicator")).append('\n');
                }
            }

            if (score >= 8 && !number.trim().isEmpty() && blockStore.isAutoBlockEnabled()) {
                blockStore.addBlocked(number, score);
                plain.append("\nProtection: this displayed number was added to your local Android block list because it scored 8–10. Caller ID can still be spoofed, so this blocks the number without claiming its subscriber is the scammer.");
                refreshProtectionStatus();
            } else if (score >= 6) {
                plain.append("\nNext step: reportable, but it was not automatically blocked because the auto-block threshold is 8/10.");
            }
            resultView.setText(plain.toString().trim());
            return;
        }

        int urls = length(result.optJSONArray("urls"));
        int emails = length(result.optJSONArray("emails"));
        int ips = length(result.optJSONArray("ipv4"));
        StringBuilder plain = new StringBuilder("Scan complete.\n\n");
        plain.append("Links found: ").append(urls)
                .append("\nEmail addresses found: ").append(emails)
                .append("\nIP addresses found: ").append(ips);
        if (urls == 0 && emails == 0 && ips == 0) {
            plain.append("\n\nNothing in this text matched WatchDog's current evidence indicators.");
        } else {
            plain.append("\n\nOpen Technical details if you want the exact extracted values and evidence hash.");
        }
        resultView.setText(plain.toString());
    }

    private void requestCallScreeningRole() {
        RoleManager roleManager = getSystemService(RoleManager.class);
        if (roleManager == null || !roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
            protectionStatus.setText("This Android device does not expose the Call Screening role.");
            return;
        }
        if (roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) {
            protectionStatus.setText("Call screening is already enabled for WatchDog.");
            return;
        }
        startActivityForResult(roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), CALL_SCREENING_REQUEST);
    }

    private void refreshProtectionStatus() {
        RoleManager roleManager = getSystemService(RoleManager.class);
        boolean roleHeld = roleManager != null
                && roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)
                && roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING);
        int count = blockStore == null ? 0 : blockStore.getBlockedNumbers().size();
        if (protectionStatus != null) {
            protectionStatus.setText(
                    "Call screening: " + (roleHeld ? "ON" : "OFF")
                            + "\nLocally blocked numbers: " + count
                            + "\nAuto-block threshold: 8/10");
        }
    }

    private void showBlockedNumbers() {
        Set<String> numbers = blockStore.getBlockedNumbers();
        if (numbers.isEmpty()) {
            new AlertDialog.Builder(this)
                    .setTitle("Blocked numbers")
                    .setMessage("No numbers are currently blocked by WatchDog.")
                    .setPositiveButton("OK", null)
                    .show();
            return;
        }
        List<String> sorted = new ArrayList<>(numbers);
        Collections.sort(sorted);
        StringBuilder message = new StringBuilder();
        for (String number : sorted) {
            message.append(number).append("  — score ").append(blockStore.scoreFor(number)).append("/10\n");
        }
        new AlertDialog.Builder(this)
                .setTitle("Blocked numbers")
                .setMessage(message.toString().trim())
                .setPositiveButton("OK", null)
                .show();
    }

    private void unblockCurrentNumber() {
        String number = numberField.getText().toString().trim();
        if (number.isEmpty()) {
            resultView.setText("Enter the phone number you want to unblock first.");
            return;
        }
        blockStore.removeBlocked(number);
        refreshProtectionStatus();
        resultView.setText("That displayed number has been removed from WatchDog's local block list.");
    }

    private void showTechnicalDetails() {
        String message = lastTechnical == null
                ? "Run a scan first."
                : lastTechnical.toString(2);
        new AlertDialog.Builder(this)
                .setTitle("Technical details")
                .setMessage(message)
                .setPositiveButton("OK", null)
                .show();
    }

    private void loadSavedConnection() {
        String apiUrl = secureStore.getString("api_url");
        String token = secureStore.getString("mobile_token");
        if (apiUrl != null) apiField.setText(apiUrl);
        deviceField.setText("My Android phone");
        if (apiUrl != null && token != null) {
            connectionStatus.setText("Paired. Share or select text in another app and choose WatchDog to scan it.");
        }
    }

    private void handleIncomingIntent(Intent intent) {
        if (intent == null || scanField == null) return;
        String action = intent.getAction();
        CharSequence shared = null;
        if (Intent.ACTION_SEND.equals(action) && "text/plain".equals(intent.getType())) {
            shared = intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
        } else if (Intent.ACTION_PROCESS_TEXT.equals(action)) {
            shared = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT);
        }
        if (shared == null || shared.toString().trim().isEmpty()) return;
        scanField.setText(shared.toString());
        resultView.setText("Shared text received. WatchDog is scanning it now.");
        if (secureStore.getString("mobile_token") != null) scanNow();
    }

    private LinearLayout card() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(16), dp(16), dp(16));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(17, 23, 32));
        background.setCornerRadius(dp(18));
        background.setStroke(dp(1), Color.rgb(41, 80, 94));
        card.setBackground(background);
        return card;
    }

    private LinearLayout.LayoutParams cardParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 0, 0, dp(14));
        return params;
    }

    private TextView sectionTitle(String value) {
        TextView view = text(value, 19, Color.WHITE, true);
        view.setPadding(0, 0, 0, dp(5));
        return view;
    }

    private TextView sectionDescription(String value) {
        TextView view = text(value, 14, Color.rgb(174, 191, 200), false);
        view.setLineSpacing(0, 1.12f);
        view.setPadding(0, 0, 0, dp(10));
        return view;
    }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private EditText field(String hint, boolean password, boolean multiline) {
        EditText input = new EditText(this);
        input.setHint(hint);
        input.setHintTextColor(Color.rgb(108, 128, 139));
        input.setTextColor(Color.WHITE);
        input.setTextSize(15);
        input.setPadding(dp(12), dp(11), dp(12), dp(11));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(9, 14, 20));
        background.setCornerRadius(dp(12));
        background.setStroke(dp(1), Color.rgb(40, 57, 68));
        input.setBackground(background);
        if (password) input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        if (multiline) {
            input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
            input.setGravity(Gravity.TOP | Gravity.START);
            input.setMinLines(5);
        }
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 0, 0, dp(9));
        input.setLayoutParams(params);
        return input;
    }

    private Button button(String label, View.OnClickListener listener, boolean secondary) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(Color.WHITE);
        button.setAllCaps(false);
        button.setTextSize(14);
        button.setOnClickListener(listener);
        GradientDrawable background = new GradientDrawable();
        background.setColor(secondary ? Color.rgb(25, 31, 40) : Color.rgb(19, 65, 77));
        background.setCornerRadius(dp(12));
        background.setStroke(dp(1), secondary ? Color.rgb(58, 70, 82) : Color.rgb(78, 156, 173));
        button.setBackground(background);
        button.setPadding(dp(12), dp(10), dp(12), dp(10));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, dp(3), 0, dp(8));
        button.setLayoutParams(params);
        return button;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static int length(JSONArray array) {
        return array == null ? 0 : array.length();
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty() ? error.getClass().getSimpleName() : message;
    }
}
