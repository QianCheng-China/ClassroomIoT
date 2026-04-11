package com.classroom.iot

import android.app.Application
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Process
import android.provider.Settings
import android.widget.Toast
import com.classroom.iot.util.PreferenceManager

class ClassroomIoTApp : Application() {
    lateinit var prefs: PreferenceManager
        private set

    override fun onCreate() {
        super.onCreate()

        // ====== 【加固】封闭系统 ADB 调试检测 ======
        if (Settings.Global.getInt(contentResolver, Settings.Global.ADB_ENABLED, 0) == 1) {
            Toast.makeText(this, "设备环境异常，应用终止", Toast.LENGTH_LONG).show()
            Thread {
                Thread.sleep(1500)
                Process.killProcess(Process.myPid())
            }.start()
            return
        }
        // =========================================

        prefs = PreferenceManager(this)
    }

    // 判断当前是否有可用网络
    fun isNetworkAvailable(): Boolean {
        val cm = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val cap = cm.getNetworkCapabilities(network) ?: return false
        return cap.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}
