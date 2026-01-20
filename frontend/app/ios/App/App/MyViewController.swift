import UIKit
import Capacitor

class MyViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(BackupProcessorPlugin())
        bridge?.registerPluginInstance(FileTransferPlugin())
        bridge?.registerPluginInstance(NativeCookiesPlugin())
    }
}
