package iph.downloader;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.JsResult;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.IOException;
import java.util.Timer;
import java.util.TimerTask;

public class MainActivity extends AppCompatActivity {

    @SuppressLint("StaticFieldLeak")
    public static MainActivity activity;
    private WebView webView;
    private PackageReceiver packageReceiver;
    private int backCount = 0;

    private String host = null;
    private static final String HostPrefKey = "Host";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        activity = this;

        try {
            packageReceiver = new PackageReceiver(10018);
        } catch (IOException e) {
            e.printStackTrace();
        }

        setContentView(R.layout.activity_main);
        webView = findViewById(R.id.webView);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                view.loadUrl("javascript:window.is_hybrid_app = true;");
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onJsAlert(WebView view, String url, String message, final JsResult result) {
                Toast.makeText(activity, message, Toast.LENGTH_LONG).show();
                Log.d("WebView", "alert: " + message);
                result.confirm();
                return true;
            }
        });
        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);

        // 从 SharedPreferences 获取字典
        SharedPreferences sharedPreferences = getSharedPreferences("IPH_Pref", MODE_PRIVATE);
        String hostUrl = sharedPreferences.getString(HostPrefKey, null);
        if (hostUrl != null) {
            LoadHost(hostUrl);
        }

        Load(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent); // 如果你想后续调用 getIntent() 返回新的 Intent，则需要这一行
        Load(intent);
    }

    private void Load(Intent intent) {
        Uri data = intent.getData();
        if (data == null) {
            return;
        }

        LoadHost(data.getHost());
    }

    private void LoadHost(String hostUrl) {
        if (host != null && host.equals(hostUrl)) {
            return;
        }

        host = hostUrl;

        SharedPreferences sharedPreferences = getSharedPreferences("IPH_Pref", MODE_PRIVATE);
        SharedPreferences.Editor editor = sharedPreferences.edit();
        editor.putString(HostPrefKey, host);
        editor.apply();

        TextView textView = findViewById(R.id.textViewCenter);
        textView.setVisibility(View.GONE);

        String url = "https://" + hostUrl;
        webView.loadUrl(url);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (packageReceiver != null) {
            packageReceiver.closeAllConnections();
            packageReceiver = null;
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if ((keyCode == KeyEvent.KEYCODE_BACK) && webView.canGoBack()) {
            webView.goBack();
            return true;
        }

        if (backCount < 1) {
            backCount++;
            Toast.makeText(this, "再按一次退出", Toast.LENGTH_SHORT).show();
            Timer timer = new Timer();
            timer.schedule(new TimerTask() {
                @Override
                public void run() {
                    backCount = 0;
                }
            }, 2000);

            return true;
        }

        return super.onKeyDown(keyCode, event);
    }

    public void InstallApk(String path) {
        File apkFile = new File(path);
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            Uri contentUri = FileProvider.getUriForFile(this, "iph.downloader.provider", apkFile);
            intent.setDataAndType(contentUri, "application/vnd.android.package-archive");
        } else {
            intent.setDataAndType(Uri.fromFile(apkFile), "application/vnd.android.package-archive");
        }
        startActivity(intent);
    }

    public void OnHashCheckError() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(R.string.hash_error)
                .setPositiveButton(R.string.reload, (dialog, id) -> webView.reload())
                .setNegativeButton(R.string.cancel, null);
        builder.create().show();
    }

    public String GetCacheDir() {
        String cacheDir;
        if (Environment.MEDIA_MOUNTED.equals(Environment.getExternalStorageState())
                || !Environment.isExternalStorageRemovable()) {
            cacheDir = getExternalCacheDir().getPath();
        } else {
            cacheDir = getCacheDir().getPath();
        }
        return cacheDir;
    }
}