import Foundation
import Capacitor

@objc(DeviceCountryPlugin)
public class DeviceCountryPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "DeviceCountryPlugin"
    public let jsName = "DeviceCountry"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "getCountryCodes", returnType: CAPPluginReturnPromise),
    ]

    @objc func getCountryCodes(_ call: CAPPluginCall) {
        var result: [String: Any] = [:]
        if let region = currentRegion() {
            result["region"] = region
        }
        call.resolve(result)
    }

    private func currentRegion() -> String? {
        let code: String?
        if #available(iOS 16, *) {
            code = Locale.current.region?.identifier
        } else {
            code = Locale.current.regionCode
        }
        guard let value = code?.uppercased(), value.count == 2 else { return nil }
        return value
    }
}
