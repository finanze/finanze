package me.finanze;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

import ee.forgr.capacitor.social.login.GoogleProvider;
import ee.forgr.capacitor.social.login.SocialLoginPlugin;
import ee.forgr.capacitor.social.login.ModifiedMainActivityForSocialLoginPlugin;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginHandle;

import me.finanze.plugins.BackupProcessorPlugin;
import me.finanze.plugins.FileTransferPlugin;
import me.finanze.plugins.ImageProcessorPlugin;
import me.finanze.plugins.NativeCookiesPlugin;
import me.finanze.plugins.LoginWebViewPlugin;
import me.finanze.plugins.TlsHttpPlugin;

public class MainActivity extends BridgeActivity implements ModifiedMainActivityForSocialLoginPlugin {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(BackupProcessorPlugin.class);
        registerPlugin(FileTransferPlugin.class);
        registerPlugin(ImageProcessorPlugin.class);
        registerPlugin(NativeCookiesPlugin.class);
        registerPlugin(LoginWebViewPlugin.class);
        registerPlugin(TlsHttpPlugin.class);
        super.onCreate(savedInstanceState);
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode >= GoogleProvider.REQUEST_AUTHORIZE_GOOGLE_MIN && requestCode < GoogleProvider.REQUEST_AUTHORIZE_GOOGLE_MAX) {
            PluginHandle pluginHandle = getBridge().getPlugin("SocialLogin");
            if (pluginHandle == null) {
                Log.i("Google Activity Result", "SocialLogin login handle is null");
                return;
            }
            Plugin plugin = pluginHandle.getInstance();
            if (!(plugin instanceof SocialLoginPlugin)) {
                Log.i("Google Activity Result", "SocialLogin plugin instance is not SocialLoginPlugin");
                return;
            }
            ((SocialLoginPlugin) plugin).handleGoogleLoginIntent(requestCode, data);
        }
    }

    @Override
    public void IHaveModifiedTheMainActivityForTheUseWithSocialLoginPlugin() {
    }
}
