package com.classroom.iot

import android.app.Application
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import com.classroom.iot.util.PreferenceManager

class ClassroomIoTApp : Application() {
    lateinit var prefs: PreferenceManager private set
    override fun onCreate() {
        super.onCreate()
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
