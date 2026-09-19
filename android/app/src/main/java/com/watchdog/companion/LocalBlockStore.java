package com.watchdog.companion;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

final class LocalBlockStore {
    private static final String PREFS = "watchdog_protection";
    private static final String KEY_BLOCKED = "blocked_numbers";
    private static final String KEY_AUTO_BLOCK = "auto_block_8_10";

    private final SharedPreferences prefs;

    LocalBlockStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    boolean isAutoBlockEnabled() {
        return prefs.getBoolean(KEY_AUTO_BLOCK, true);
    }

    void setAutoBlockEnabled(boolean enabled) {
        prefs.edit().putBoolean(KEY_AUTO_BLOCK, enabled).apply();
    }

    boolean isBlocked(String number) {
        String normalized = normalize(number);
        return !normalized.isEmpty() && getBlockedNumbers().contains(normalized);
    }

    void addBlocked(String number, int score) {
        String normalized = normalize(number);
        if (normalized.isEmpty()) return;
        Set<String> updated = new HashSet<>(getBlockedNumbers());
        updated.add(normalized);
        prefs.edit()
                .putStringSet(KEY_BLOCKED, updated)
                .putInt("score_" + normalized, score)
                .apply();
    }

    void removeBlocked(String number) {
        String normalized = normalize(number);
        if (normalized.isEmpty()) return;
        Set<String> updated = new HashSet<>(getBlockedNumbers());
        updated.remove(normalized);
        prefs.edit().putStringSet(KEY_BLOCKED, updated).remove("score_" + normalized).apply();
    }

    Set<String> getBlockedNumbers() {
        Set<String> stored = prefs.getStringSet(KEY_BLOCKED, Collections.emptySet());
        return stored == null ? Collections.emptySet() : new HashSet<>(stored);
    }

    int scoreFor(String number) {
        String normalized = normalize(number);
        return prefs.getInt("score_" + normalized, 0);
    }

    static String normalize(String value) {
        if (value == null) return "";
        String digits = value.replaceAll("\\D", "");
        if (digits.length() > 20) digits = digits.substring(0, 20);
        return digits;
    }
}
