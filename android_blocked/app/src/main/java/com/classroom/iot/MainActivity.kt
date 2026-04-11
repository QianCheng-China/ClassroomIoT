package com.classroom.iot
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.classroom.iot.databinding.ActivityMainBinding
import android.content.Intent

class MainActivity : BaseActivity() {
    private lateinit var b: ActivityMainBinding
    override fun onCreate(s: Bundle?) {
        super.onCreate(s);
        val prefs = (application as ClassroomIoTApp).prefs
        if (!prefs.isLoggedIn) {
            startActivity(Intent(this, ServerListActivity::class.java))
            finish() // 销毁当前 Main 页面，防止用户按返回键空转
            return
        }
        b = ActivityMainBinding.inflate(layoutInflater); setContentView(b.root)
        val isOnline = (application as ClassroomIoTApp).prefs.isLoggedIn
        b.bottomNav.setOnItemSelectedListener { item ->
            when(item.itemId) {
                R.id.nav_function -> { supportFragmentManager.beginTransaction().replace(R.id.fragmentContainer, FunctionFragment.newInstance(isOnline)).commit(); true }
                R.id.nav_mine -> { supportFragmentManager.beginTransaction().replace(R.id.fragmentContainer, MineFragment.newInstance()).commit(); true }
                else -> false
            }
        }
        b.bottomNav.selectedItemId = R.id.nav_function
    }
}
