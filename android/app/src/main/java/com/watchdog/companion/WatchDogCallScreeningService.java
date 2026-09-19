package com.watchdog.companion;

import android.net.Uri;
import android.telecom.Call;
import android.telecom.CallScreeningService;

public final class WatchDogCallScreeningService extends CallScreeningService {
    @Override
    public void onScreenCall(Call.Details callDetails) {
        if (callDetails.getCallDirection() != Call.Details.DIRECTION_INCOMING) {
            return;
        }

        Uri handle = callDetails.getHandle();
        String number = handle == null ? "" : handle.getSchemeSpecificPart();
        LocalBlockStore store = new LocalBlockStore(this);
        boolean blocked = store.isBlocked(number);

        CallResponse.Builder builder = new CallResponse.Builder();
        if (blocked) {
            builder.setDisallowCall(true)
                    .setRejectCall(true)
                    .setSkipCallLog(false)
                    .setSkipNotification(false);
        } else {
            builder.setDisallowCall(false)
                    .setRejectCall(false)
                    .setSkipCallLog(false)
                    .setSkipNotification(false);
        }
        respondToCall(callDetails, builder.build());
    }
}
