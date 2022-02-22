package iph.downloader;

import android.os.Environment;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
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
            String path = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS).getAbsolutePath();
            File outputFile = new File(path + "/" + Objects.requireNonNull(params.get("file")).get(0));
            outputFile.createNewFile();
            FileOutputStream outputStream = new FileOutputStream(outputFile);

            InputStream inputStream = session.getInputStream();
            byte[] buffer = new byte[1024 * 1024];
            int n;
            int sum = 0;
            do {
                n = inputStream.read(buffer);
                sum += n;
                outputStream.write(buffer, 0, n);
            } while (sum < total);

            Log.d("PackageReceiver", "received: " + sum);
            outputStream.close();
            MainActivity.activity.InstallApk(outputFile.getAbsolutePath());
        } catch (IOException e) {
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
