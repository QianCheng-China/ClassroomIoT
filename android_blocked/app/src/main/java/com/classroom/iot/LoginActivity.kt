package com.classroom.iot

import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.classroom.iot.databinding.ActivityLoginBinding
import com.classroom.iot.model.LoginResponse
import com.classroom.iot.model.ServerInfo
import com.classroom.iot.network.ApiClient
import com.classroom.iot.util.PreferenceManager
import kotlinx.coroutines.launch
import java.security.MessageDigest

class LoginActivity : BaseActivity() {
    private lateinit var b: ActivityLoginBinding
    private lateinit var prefs: PreferenceManager
    private lateinit var currentServer: ServerInfo

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        b = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(b.root)
        prefs = (application as ClassroomIoTApp).prefs

        val name = intent.getStringExtra("server_name") ?: ""
        val ip = intent.getStringExtra("server_ip") ?: ""
        val port = intent.getIntExtra("server_port", 8080)

        if (ip.isBlank()) { finish(); return }
        currentServer = ServerInfo(name, ip, port)

        b.tvSelectedServer.text = "${currentServer.name} (${currentServer.ip}:${currentServer.port})"
        b.btnBack.setOnClickListener { finish() }
        b.btnLogin.setOnClickListener { doLogin() }

        b.rootLogin.setOnTouchListener { _, event ->
            if (event.action == MotionEvent.ACTION_DOWN) {
                currentFocus?.let {
                    val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
                    imm.hideSoftInputFromWindow(it.windowToken, 0)
                    it.clearFocus()
                }
            }
            false
        }
    }

    private fun doLogin() {
        val u = b.etUsername.text.toString().trim()
        val pw = b.etPassword.text.toString().trim()

        if (u.isBlank() || pw.isBlank()) {
            showError("请输入账号密码"); return
        }

        if (!(application as ClassroomIoTApp).isNetworkAvailable()) {
            showError("检查Internet连接"); return
        }

        b.btnLogin.isEnabled = false
        b.btnBack.isEnabled = false
        b.btnLogin.text = "登录中…"
        b.layoutMessage.visibility = View.GONE

        lifecycleScope.launch {
            try {
                val r: LoginResponse = ApiClient(currentServer.baseUrl).login(u, sha256(pw))
                if (r.success) {
                    prefs.serverIp = currentServer.ip
                    prefs.serverPort = currentServer.port
                    if (currentServer.name == "手输") {
                        try { prefs.serverName = ApiClient(currentServer.baseUrl).getServerInfo().name }
                        catch (_: Exception) { prefs.serverName = "手输" }
                    } else { prefs.serverName = currentServer.name }

                    prefs.token = r.token
                    prefs.username = u
                    prefs.isLoggedIn = true
                    goMain()
                } else { showError(r.error.ifBlank { "登录失败" }) }
            } catch (e: Exception) { showError("连接失败") }
            finally { runOnUiThread { b.btnLogin.isEnabled = true; b.btnBack.isEnabled = true; b.btnLogin.text = "登录" } }
        }
    }

    // 采用与修改密码页面一致的错误卡片提示
    private fun showError(msg: String) {
        b.layoutMessage.visibility = View.VISIBLE
        b.layoutMessage.background = null
        b.layoutMessage.background = GradientDrawable().apply {
            cornerRadius = 12f
            setColor(Color.parseColor("#FFEBEE"))
        }
        b.ivMsgIcon.setImageResource(android.R.drawable.ic_dialog_alert)
        b.ivMsgIcon.setColorFilter(Color.RED)
        b.tvMsgText.text = msg
        b.tvMsgText.setTextColor(Color.RED)
    }

    private fun goMain() { startActivity(Intent(this, MainActivity::class.java)); finish() }
    private fun sha256(s: String) = MessageDigest.getInstance("SHA-256").digest(s.toByteArray()).joinToString("") { "%02x".format(it) }
}
