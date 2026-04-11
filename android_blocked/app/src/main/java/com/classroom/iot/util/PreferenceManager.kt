package com.classroom.iot.util

import android.content.Context

class PreferenceManager(ctx: Context) {
    private val p = ctx.getSharedPreferences("c_iot", Context.MODE_PRIVATE)

    var serverIp: String?
        get() = p.getString("ip", null)
        set(v) = p.edit().putString("ip", v).apply()

    var serverPort: Int
        get() = p.getInt("port", 8080)
        set(v) = p.edit().putInt("port", v).apply()

    var serverName: String?
        get() = p.getString("name", null)
        set(v) = p.edit().putString("name", v).apply()

    var token: String?
        get() = p.getString("token", null)
        set(v) = p.edit().putString("token", v).apply()

    // 👇 就是这里：新增的 username 属性
    var username: String?
        get() = p.getString("username", null)
        set(v) = p.edit().putString("username", v).apply()

    var isLoggedIn: Boolean
        get() = p.getBoolean("in", false)
        set(v) = p.edit().putBoolean("in", v).apply()

    fun hasPrev(): Boolean = !serverIp.isNullOrEmpty() && !token.isNullOrEmpty()

    fun clear() = p.edit().clear().apply()
}
