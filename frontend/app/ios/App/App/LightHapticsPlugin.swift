import UIKit
import Capacitor

@objc(LightHapticsPlugin)
public class LightHapticsPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "LightHapticsPlugin"
    public let jsName = "LightHaptics"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "prepare", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "impact", returnType: CAPPluginReturnPromise),
    ]

    private var lightImpactGenerator: UIImpactFeedbackGenerator?

    @objc func prepare(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.getLightImpactGenerator().prepare()
            call.resolve()
        }
    }

    @objc func impact(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            let generator = self.getLightImpactGenerator()
            generator.impactOccurred()
            generator.prepare()
            call.resolve()
        }
    }

    private func getLightImpactGenerator() -> UIImpactFeedbackGenerator {
        if let generator = lightImpactGenerator {
            return generator
        }

        let generator = UIImpactFeedbackGenerator(style: .light)
        lightImpactGenerator = generator
        return generator
    }
}