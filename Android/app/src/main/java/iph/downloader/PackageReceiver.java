package iph.downloader;

import android.util.Log;

import java.io.IOException;
import java.io.InputStream;
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
        Log.d("PackageReceiver", "receive start");

        Map<String, String> headers = session.getHeaders();
        int total = Integer.parseInt(Objects.requireNonNull(headers.get("content-length")));

        try {
            InputStream inputStream = session.getInputStream();
            byte[] buffer = new byte[1024 * 1024];
            int n;
            int sum = 0;
            do {
                n = inputStream.read(buffer);
                sum += n;
            } while (sum < total);
            Log.d("PackageReceiver", "received: " + sum);
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
