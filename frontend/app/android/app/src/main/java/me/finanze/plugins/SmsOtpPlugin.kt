package me.finanze.plugins

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import androidx.activity.result.ActivityResult
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import com.google.android.gms.auth.api.phone.SmsRetriever
import com.google.android.gms.common.api.CommonStatusCodes
import com.google.android.gms.common.api.Status

@CapacitorPlugin(name = "SmsOtp")
class SmsOtpPlugin : Plugin() {

    companion object {
        private const val EVENT_SMS_RECEIVED = "smsReceived"
    }

    private var smsReceiver: BroadcastReceiver? = null
    private var listening = false
    private var sessionActive = false
    private var startCall: PluginCall? = null

    @PluginMethod
    fun startListening(call: PluginCall) {
        if (sessionActive && listening) {
            call.resolve()
            return
        }

        sessionActive = true
        retainStartCall(call)
        beginConsent { success, error ->
            if (success) {
                call.resolve()
            } else {
                sessionActive = false
                releaseStartCall()
                if (error != null) {
                    call.reject("Failed to start SMS user consent: ${error.message}", error)
                } else {
                    call.reject("Failed to start SMS user consent")
                }
            }
        }
    }

    @PluginMethod
    fun stopListening(call: PluginCall) {
        stopInternal()
        call.resolve()
    }

    @ActivityCallback
    fun handleConsentResult(call: PluginCall?, result: ActivityResult) {
        listening = false
        unregisterSmsReceiver()

        if (result.resultCode == Activity.RESULT_OK && sessionActive) {
            val message = result.data?.getStringExtra(SmsRetriever.EXTRA_SMS_MESSAGE)
            if (!message.isNullOrBlank()) {
                val payload = JSObject()
                payload.put("message", message)
                notifyListeners(EVENT_SMS_RECEIVED, payload, true)
            }
        }
        if (sessionActive) {
            beginConsent()
        }
    }

    override fun handleOnDestroy() {
        stopInternal()
        super.handleOnDestroy()
    }

    private fun beginConsent(onDone: ((Boolean, Exception?) -> Unit)? = null) {
        SmsRetriever.getClient(context)
            .startSmsUserConsent(null)
            .addOnSuccessListener {
                registerSmsReceiver()
                listening = true
                onDone?.invoke(true, null)
            }
            .addOnFailureListener { error ->
                listening = false
                onDone?.invoke(false, error)
            }
    }

    private fun stopInternal() {
        sessionActive = false
        listening = false
        unregisterSmsReceiver()
        releaseStartCall()
    }

    private fun retainStartCall(call: PluginCall) {
        startCall?.setKeepAlive(false)
        startCall?.let { bridge.releaseCall(it) }
        call.setKeepAlive(true)
        bridge.saveCall(call)
        startCall = call
    }

    private fun releaseStartCall() {
        val call = startCall ?: return
        call.setKeepAlive(false)
        bridge.releaseCall(call)
        startCall = null
    }

    private fun registerSmsReceiver() {
        if (smsReceiver != null) return

        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                try {
                    handleSmsRetrieved(intent)
                } catch (_: Exception) {
                }
            }
        }

        smsReceiver = receiver
        val filter = IntentFilter(SmsRetriever.SMS_RETRIEVED_ACTION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.registerReceiver(
                receiver,
                filter,
                SmsRetriever.SEND_PERMISSION,
                null,
                Context.RECEIVER_EXPORTED,
            )
        } else {
            context.registerReceiver(
                receiver,
                filter,
                SmsRetriever.SEND_PERMISSION,
                null,
            )
        }
    }

    private fun handleSmsRetrieved(intent: Intent?) {
        if (intent?.action != SmsRetriever.SMS_RETRIEVED_ACTION) return

        val extras = intent.extras ?: return
        extras.classLoader = Status::class.java.classLoader
        val status = extras.get(SmsRetriever.EXTRA_STATUS) as? Status ?: return

        when (status.statusCode) {
            CommonStatusCodes.SUCCESS -> {
                @Suppress("DEPRECATION")
                val consentIntent =
                    extras.getParcelable<Intent>(SmsRetriever.EXTRA_CONSENT_INTENT) ?: return
                val pendingCall = startCall ?: return
                activity.runOnUiThread {
                    try {
                        startActivityForResult(
                            pendingCall,
                            consentIntent,
                            "handleConsentResult",
                        )
                    } catch (_: Exception) {
                    }
                }
            }
            CommonStatusCodes.TIMEOUT -> {
                listening = false
                unregisterSmsReceiver()
                if (sessionActive) {
                    activity.runOnUiThread { beginConsent() }
                }
            }
        }
    }

    private fun unregisterSmsReceiver() {
        val receiver = smsReceiver ?: return
        try {
            context.unregisterReceiver(receiver)
        } catch (_: IllegalArgumentException) {
        }
        smsReceiver = null
    }
}
