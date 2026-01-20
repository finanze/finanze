package finanze.me;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

import finanze.me.plugins.BackupProcessorPlugin;
import finanze.me.plugins.FileTransferPlugin;
import finanze.me.plugins.NativeCookiesPlugin;

public class MainActivity extends BridgeActivity {
	@Override
	public void onCreate(Bundle savedInstanceState) {
		registerPlugin(BackupProcessorPlugin.class);
		registerPlugin(FileTransferPlugin.class);
		registerPlugin(NativeCookiesPlugin.class);
		super.onCreate(savedInstanceState);
	}
}
