package com.classroom.iot.util
import android.util.Log
import com.classroom.iot.model.ServerInfo
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.util.concurrent.CopyOnWriteArrayList
object UdpDiscovery {
    private val gson = Gson()
    suspend fun find(): List<ServerInfo> = withContext(Dispatchers.IO) {
        val found = CopyOnWriteArrayList<ServerInfo>()
        val sock = DatagramSocket(47789); sock.soTimeout = 5000; sock.broadcast = true
        val buf = ByteArray(4096); val start = System.currentTimeMillis()
        try { while(System.currentTimeMillis() - start < 5000) {
            try { val pkt = DatagramPacket(buf, buf.size); sock.receive(pkt)
                val obj = gson.fromJson(String(pkt.data, 0, pkt.length), Map::class.java)
                if(obj["type"] == "classroom-iot-discovery") {
                    val info = ServerInfo(obj["name"] as? String ?: "", obj["ip"] as? String ?: continue, (obj["port"] as? Double)?.toInt() ?: 8080)
                    if(found.none { it.ip == info.ip }) found.add(info)
                }
            } catch(e: Exception) { if(e is java.net.SocketTimeoutException) break }
        }} finally { sock.close() }
        found.toList()
    }
}
