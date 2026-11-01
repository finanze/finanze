package me.finanze.plugins

import android.content.Context
import android.telephony.TelephonyManager
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin

@CapacitorPlugin(name = "DeviceCountry")
class DeviceCountryPlugin : Plugin() {

    @PluginMethod
    fun getCountryCodes(call: PluginCall) {
        val telephony = context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager

        val result = JSObject()
        result.put("network", normalize(safeRead { telephony?.networkCountryIso }))
        result.put("sim", normalize(safeRead { telephony?.simCountryIso }))
        result.put("locale", normalize(safeRead { context.resources.configuration.locales[0]?.country }))
        call.resolve(result)
    }

    private fun safeRead(read: () -> String?): String? =
        try {
            read()
        } catch (e: Exception) {
            null
        }

    private fun normalize(code: String?): String? =
        code?.trim()?.uppercase()?.takeIf { it.length == 2 }
}
