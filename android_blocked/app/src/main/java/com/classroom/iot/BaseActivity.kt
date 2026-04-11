package com.classroom.iot

import android.content.Intent
import android.os.Bundle
import android.view.ContextMenu
import android.view.View
import androidx.appcompat.app.AppCompatActivity

abstract class BaseActivity : AppCompatActivity() {

    override fun startActivity(intent: Intent?) {
        if (isSafeIntent(intent)) super.startActivity(intent)
    }

    override fun startActivity(intent: Intent?, options: android.os.Bundle?) {
        if (isSafeIntent(intent)) super.startActivity(intent, options)
    }

    // 已移除 startActivityForResult，因为现代 Android SDK (API 33+) 已将其彻底删除
    // 现代跳转统一使用上面的 startActivity 即可被完美拦截

    private fun isSafeIntent(intent: Intent?): Boolean {
        if (intent == null) return false

        // 1. 致命拦截：掐死所有隐式 Intent（极易被系统浏览器截胡）
        if (intent.component == null) {
            return false
        }

        val targetPackage = intent.component?.packageName ?: ""

        // 2. 黑名单：拦截主流浏览器包名
        val dangerousPackages = listOf(
            "com.android.browser",
            "com.tencent.mtt",
            "com.UCMobile",
            "com.opera.browser",
            "org.chromium.chrome",
            "com.miui.browser",
            "com.huawei.browser",
            "com.samsung.android.app.sbrowser"
        )

        if (dangerousPackages.any { targetPackage.contains(it) }) {
            return false
        }

        // 3. 白名单：只允许跳转到本应用内部
        if (!targetPackage.startsWith(this.packageName)) {
            return false
        }

        return true
    }

    // 【终极兜底防御】重写创建上下文菜单的方法，直接返回空
    // 这样即使某个输入框漏设了 isLongClickable = false，长按也绝对弹不出任何菜单！
    override fun onCreateContextMenu(menu: ContextMenu?, v: View?, menuInfo: ContextMenu.ContextMenuInfo?) {
        // 什么都不做，彻底禁用
    }
}
