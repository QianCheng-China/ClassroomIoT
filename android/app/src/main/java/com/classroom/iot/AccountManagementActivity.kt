package com.classroom.iot

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.classroom.iot.databinding.ActivityAccountManagementBinding

class AccountManagementActivity : AppCompatActivity() {
    private lateinit var b: ActivityAccountManagementBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityAccountManagementBinding.inflate(layoutInflater)
        setContentView(b.root)

        b.toolbarAccount.setNavigationOnClickListener { finish() }

        b.cardChangePwd.setOnClickListener {
            startActivity(Intent(this, ChangePasswordActivity::class.java))
        }

        b.cardLogout.setOnClickListener {
            AlertDialog.Builder(this).setTitle("退出").setMessage("确定退出当前账号？")
                .setPositiveButton("确定") { _, _ ->
                    (application as ClassroomIoTApp).prefs.clear()
                    // 清理任务栈并跳转到登录页
                    val intent = Intent(this, LoginActivity::class.java)
                    intent.flags = Intent.FLAG_ACTIVITY_CLEAR_TASK or Intent.FLAG_ACTIVITY_NEW_TASK
                    startActivity(intent)
                }
                .setNegativeButton("取消", null).show()
        }
    }
}
