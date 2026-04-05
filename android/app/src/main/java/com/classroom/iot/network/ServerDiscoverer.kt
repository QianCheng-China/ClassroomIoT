package com.classroom.iot.network

import android.util.Log
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket

data class ServerInfo(val ip: String, val port: Int, val name: String)

object ServerDiscoverer {
    private const val TAG = "Discoverer"
    private const val PORT = 48899

    /**
     * 开启一个后台线程监听 UDP 广播
     * @param timeoutMs 监听超时时间(毫秒)
     * @param onFound 找到服务器后的回调
     */
    fun discover(timeoutMs: Long = 3000, onFound: (ServerInfo) -> Unit) {
        Thread {
            var socket: DatagramSocket? = null
            try {
                socket = DatagramSocket(PORT)
                socket.soTimeout = timeoutMs.toInt()
                val buf = ByteArray(1024)
                val packet = DatagramPacket(buf, buf.size)

                Log.d(TAG, "开始监听服务器广播...")
                socket.receive(packet) // 阻塞等待，直到收到或者超时

                val json = String(packet.data, 0, packet.length)
                val obj = JSONObject(json)

                if (obj.getString("type") == "classroom_iot_discovery") {
                    val info = ServerInfo(
                        ip = obj.getString("ip"),
                        port = obj.getInt("port"),
                        name = obj.getString("name")
                    )
                    Log.d(TAG, "发现服务器: $info")
                    onFound(info)
                }
            } catch (e: Exception) {
                Log.d(TAG, "监听超时或异常: ${e.message}")
            } finally {
                socket?.close()
            }
        }.start()
    }
}
