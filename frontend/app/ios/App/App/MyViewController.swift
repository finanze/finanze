import UIKit
import Capacitor

class MyViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(BackupProcessorPlugin())
        bridge?.registerPluginInstance(FileTransferPlugin())
        bridge?.registerPluginInstance(NativeCookiesPlugin())
        bridge?.registerPluginInstance(ImageProcessorPlugin())
        bridge?.registerPluginInstance(PdfRendererPlugin())
        bridge?.registerPluginInstance(DeviceCountryPlugin())
        bridge?.registerPluginInstance(LightHapticsPlugin())
        bridge?.registerPluginInstance(LoopbackCallbackPlugin())
        #if CONNECTIONS
        bridge?.registerPluginInstance(LoginWebViewPlugin())
        bridge?.registerPluginInstance(TlsHttpPlugin())
        #endif
    }
}
