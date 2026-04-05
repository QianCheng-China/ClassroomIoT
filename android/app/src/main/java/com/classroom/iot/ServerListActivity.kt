package com.classroom.iot

import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.classroom.iot.databinding.ActivityServerListBinding
import com.classroom.iot.model.ServerInfo
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket

class ServerListActivity : AppCompatActivity() {
    private lateinit var b: ActivityServerListBinding
    private val serverList = mutableListOf<ServerInfo>()
    private val foundIps = mutableSetOf<String>()
    private lateinit var adapter: ServerAdapter
    private var isScanning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityServerListBinding.inflate(layoutInflater)
        setContentView(b.root)

        b.rvServers.layoutManager = LinearLayoutManager(this)
        adapter = ServerAdapter()
        b.rvServers.adapter = adapter

        b.btnManualInput.setOnClickListener { showManualDialog() }
        b.btnRescan.setOnClickListener { if (!isScanning) startDiscovery() }

        b.rootServerList.setOnTouchListener { _, event ->
            if (event.action == MotionEvent.ACTION_DOWN) {
                currentFocus?.let {
                    val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
                    imm.hideSoftInputFromWindow(it.windowToken, 0)
                    it.clearFocus()
                }
            }
            false
        }

        startDiscovery()
    }

    private fun startDiscovery() {
        val app = application as ClassroomIoTApp

        if (!app.isNetworkAvailable()) {
            isScanning = false
            b.btnRescan.isEnabled = true
            b.btnRescan.alpha = 1.0f
            b.progressScan.visibility = View.GONE
            b.tvScanning.text = "检查Internet连接"
            return
        }

        isScanning = true
        b.btnRescan.isEnabled = false
        b.btnRescan.alpha = 0.5f
        b.progressScan.visibility = View.VISIBLE
        b.tvScanning.text = "正在扫描..."

        lifecycleScope.launch(Dispatchers.IO) {
            var socket: DatagramSocket? = null
            try {
                socket = DatagramSocket(48899)
                socket.soTimeout = 500
                val buf = ByteArray(1024)
                val packet = DatagramPacket(buf, buf.size)
                val endTime = System.currentTimeMillis() + 5000

                while (System.currentTimeMillis() < endTime) {
                    try {
                        socket.receive(packet)
                        val json = String(packet.data, 0, packet.length)
                        val obj = JSONObject(json)
                        if (obj.getString("type") == "classroom_iot_discovery") {
                            val ip = obj.getString("ip")
                            if (!foundIps.contains(ip)) {
                                foundIps.add(ip)
                                val info = ServerInfo(obj.getString("name"), ip, obj.getInt("port"))
                                withContext(Dispatchers.Main) {
                                    serverList.add(info)
                                    adapter.notifyItemInserted(serverList.size - 1)
                                }
                            }
                        }
                    } catch (e: Exception) { }
                }
            } catch (e: Exception) { } finally {
                socket?.close()
                withContext(Dispatchers.Main) {
                    isScanning = false
                    b.btnRescan.isEnabled = true
                    b.btnRescan.alpha = 1.0f
                    b.progressScan.visibility = View.GONE
                    b.tvScanning.text = "扫描完成"
                }
            }
        }
    }

    private fun showManualDialog() {
        val et = EditText(this).apply {
            hint = "例如: 192.168.1.100"
            maxLines = 1
            setPadding(48, 32, 48, 32)
            background = null
        }
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 24, 48, 24)
            background = GradientDrawable().apply { cornerRadius = 32f; setColor(android.graphics.Color.parseColor("#F5F5F5")) }
            addView(et)
        }
        AlertDialog.Builder(this).setTitle("手动输入 IP 地址").setView(container)
            .setPositiveButton("连接") { _, _ ->
                val ip = et.text.toString().trim()
                if (ip.isNotBlank()) goLogin(ServerInfo("手输", ip, 8080))
            }.setNegativeButton("取消", null).show()
    }

    private fun goLogin(server: ServerInfo) {
        startActivity(Intent(this, LoginActivity::class.java).apply {
            putExtra("server_name", server.name)
            putExtra("server_ip", server.ip)
            putExtra("server_port", server.port)
        })
    }

    inner class ServerAdapter : RecyclerView.Adapter<ServerAdapter.VH>() {
        inner class VH(v: View) : RecyclerView.ViewHolder(v)
        override fun onCreateViewHolder(p: ViewGroup, v: Int) = VH(LayoutInflater.from(this@ServerListActivity).inflate(R.layout.item_server, p, false))
        override fun getItemCount() = serverList.size
        override fun onBindViewHolder(h: VH, i: Int) {
            h.itemView.findViewById<TextView>(R.id.tvServerName).text = serverList[i].name
            h.itemView.findViewById<TextView>(R.id.tvServerIp).text = "${serverList[i].ip}:${serverList[i].port}"
            h.itemView.setOnClickListener { goLogin(serverList[i]) }
        }
    }
}
