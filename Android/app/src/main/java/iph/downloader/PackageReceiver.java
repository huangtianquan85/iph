package iph.downloader;

import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import fi.iki.elonen.NanoHTTPD;

public class PackageReceiver extends NanoHTTPD {

    public PackageReceiver(int port) throws IOException {
        super(port);
        start(30000);
    }

    @Override
    public Response serve(IHTTPSession session) {
        Map<String, List<String>> params = session.getParameters();
        Map<String, String> headers = session.getHeaders();
        int total = Integer.parseInt(Objects.requireNonNull(headers.get("content-length")));

        try {
            File apkCacheDir = new File(MainActivity.activity.getCacheDir() + "/apk_cache");
            if (!apkCacheDir.exists()) {
                apkCacheDir.mkdir();
            }

            File outputFile = new File(apkCacheDir.getPath() + "/temp.apk");
            outputFile.createNewFile();
            FileOutputStream outputStream = new FileOutputStream(outputFile);

            MessageDigest md = MessageDigest.getInstance("MD5");

            InputStream inputStream = session.getInputStream();
            byte[] buffer = new byte[1024 * 1024];
            int n;
            int sum = 0;
            do {
                n = inputStream.read(buffer);
                sum += n;
                outputStream.write(buffer, 0, n);
                md.update(buffer, 0, n);
            } while (sum < total);

            Log.d("PackageReceiver", "received: " + sum);
            outputStream.close();

            StringBuilder hashBuilder = new StringBuilder();
            for (byte i : md.digest()) {
                hashBuilder.append(String.format("%02x", i));
            }

            new Thread(() -> MainActivity.activity.runOnUiThread(() -> {
                if (hashBuilder.toString().equals(Objects.requireNonNull(params.get("hash")).get(0))) {
                    MainActivity.activity.InstallApk(outputFile.getAbsolutePath());
                } else {
                    outputFile.delete();
                    MainActivity.activity.OnHashCheckError();
                }
            })).start();
        } catch (IOException | NoSuchAlgorithmException e) {
            e.printStackTrace();
        }

        try {
            Response resp = newFixedLengthResponse("");
            resp.addHeader("Access-Control-Allow-Origin", "*");
            return resp;
        } catch (Exception exception) {
            return newFixedLengthResponse(Response.Status.INTERNAL_ERROR, MIME_PLAINTEXT, "Internal Server Error");
        }
    }
}
