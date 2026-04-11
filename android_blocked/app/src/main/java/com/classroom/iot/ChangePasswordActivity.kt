package com.classroom.iot

import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.classroom.iot.databinding.ActivityChangePasswordBinding
import com.classroom.iot.network.ApiClient
import kotlinx.coroutines.launch

class ChangePasswordActivity : BaseActivity() {
    private lateinit var b: ActivityChangePasswordBinding
    private lateinit var api: ApiClient
    private var isShowingNetworkMsg = false // 防止网络结果被焦点事件覆盖

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityChangePasswordBinding.inflate(layoutInflater)
        setContentView(b.root)

        val p = (application as ClassroomIoTApp).prefs
        api = ApiClient("http://${p.serverIp}:${p.serverPort}")

        b.toolbarChangePwd.setNavigationOnClickListener { finish() }

        // 点击空白收起键盘并清除焦点
        b.rootChangePwd.setOnTouchListener { _, event ->
            if (event.action == MotionEvent.ACTION_DOWN) {
                currentFocus?.let {
                    val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
                    imm.hideSoftInputFromWindow(it.windowToken, 0)
                    it.clearFocus()
                }
            }
            false
        }

        val textWatcher = object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: android.text.Editable?) {
                // 只要有输入，立刻清除网络提示标记
                if (isShowingNetworkMsg) {
                    isShowingNetworkMsg = false
                    b.layoutMessage.visibility = View.GONE
                }
                updateUIStatus()
            }
        }
        b.etOldPwd.addTextChangedListener(textWatcher)
        b.etNewPwd.addTextChangedListener(textWatcher)
        b.etConfirmPwd.addTextChangedListener(textWatcher)

        b.etNewPwd.setOnFocusChangeListener { _, _ -> updateUIStatus() }
        b.etConfirmPwd.setOnFocusChangeListener { _, _ -> updateUIStatus() }
        b.etOldPwd.setOnFocusChangeListener { _, _ -> updateUIStatus() }

        b.btnSubmitPwd.setOnClickListener {
            if (!b.btnSubmitPwd.isEnabled) return@setOnClickListener
            doChangePassword()
        }
        updateUIStatus()
    }

    private fun updateUIStatus() {
        // 如果正在显示网络请求结果，只更新按钮状态，不覆盖提示框
        if (isShowingNetworkMsg) {
            val old = b.etOldPwd.text.toString()
            val new = b.etNewPwd.text.toString()
            val confirm = b.etConfirmPwd.text.toString()
            setBtnEnabled(old.isNotEmpty() && new.isNotEmpty() && confirm.isNotEmpty() && new == confirm && new != old)
            return
        }

        val oldPwd = b.etOldPwd.text.toString()
        val newPwd = b.etNewPwd.text.toString()
        val confirmPwd = b.etConfirmPwd.text.toString()
        val isNewFocused = b.etNewPwd.hasFocus()
        val isConfirmFocused = b.etConfirmPwd.hasFocus()

        if (isNewFocused || isConfirmFocused) {
            b.layoutStrength.visibility = View.VISIBLE
            b.layoutMessage.visibility = View.GONE
            updateStrengthUI(newPwd)
        } else if (newPwd.isNotEmpty() && confirmPwd.isNotEmpty() && newPwd != confirmPwd) {
            b.layoutStrength.visibility = View.GONE
            showMessage(false, "新密码与确认密码不一致", Color.parseColor("#FFEBEE"), Color.RED)
            setBtnEnabled(false)
            return
        } else if (newPwd.isNotEmpty() && newPwd == oldPwd) {
            // 新增逻辑：新密码不能与原密码相同
            b.layoutStrength.visibility = View.GONE
            showMessage(false, "新密码不能与原密码相同", Color.parseColor("#FFEBEE"), Color.RED)
            setBtnEnabled(false)
            return
        } else {
            b.layoutStrength.visibility = View.VISIBLE
            b.layoutMessage.visibility = View.GONE
            updateStrengthUI(newPwd)
        }

        if (oldPwd.isEmpty() || newPwd.isEmpty() || confirmPwd.isEmpty() || newPwd != confirmPwd || newPwd == oldPwd) {
            setBtnEnabled(false)
        } else {
            setBtnEnabled(true)
        }
    }

    private fun updateStrengthUI(pwd: String) {
        val gray = Color.parseColor("#E0E0E0")
        b.bar1.setBackgroundColor(gray); b.bar2.setBackgroundColor(gray)
        b.bar3.setBackgroundColor(gray); b.bar4.setBackgroundColor(gray); b.bar5.setBackgroundColor(gray)
        b.tvStrengthText.text = ""; b.tvStrengthText.setTextColor(gray)

        if (pwd.isEmpty()) return

        b.bar1.setBackgroundColor(Color.parseColor("#F44336"))
        b.tvStrengthText.text = "非常弱"; b.tvStrengthText.setTextColor(Color.parseColor("#F44336"))

        var level = 1
        val hasLetter = pwd.any { it.isLetter() }
        val hasDigit = pwd.any { it.isDigit() }
        val hasSpecial = pwd.any { !it.isLetterOrDigit() }
        val hasUpper = pwd.any { it.isUpperCase() }
        val hasLower = pwd.any { it.isLowerCase() }

        if (pwd.length >= 4 && hasLetter) level = 2
        if (pwd.length >= 6 && hasLetter && hasDigit) level = 3
        if (pwd.length >= 8 && hasLetter && hasDigit && hasSpecial) level = 4
        if (pwd.length >= 10 && hasUpper && hasLower && hasDigit && hasSpecial) level = 5

        when (level) {
            2 -> { b.bar2.setBackgroundColor(Color.parseColor("#FF9800")); b.tvStrengthText.text = "较弱"; b.tvStrengthText.setTextColor(Color.parseColor("#FF9800")) }
            3 -> { b.bar2.setBackgroundColor(Color.parseColor("#FFC107")); b.bar3.setBackgroundColor(Color.parseColor("#FFC107")); b.tvStrengthText.text = "中等"; b.tvStrengthText.setTextColor(Color.parseColor("#FFC107")) }
            4 -> { b.bar2.setBackgroundColor(Color.parseColor("#4CAF50")); b.bar3.setBackgroundColor(Color.parseColor("#4CAF50")); b.bar4.setBackgroundColor(Color.parseColor("#4CAF50")); b.tvStrengthText.text = "强"; b.tvStrengthText.setTextColor(Color.parseColor("#4CAF50")) }
            5 -> { b.bar2.setBackgroundColor(Color.parseColor("#2196F3")); b.bar3.setBackgroundColor(Color.parseColor("#2196F3")); b.bar4.setBackgroundColor(Color.parseColor("#2196F3")); b.bar5.setBackgroundColor(Color.parseColor("#2196F3")); b.tvStrengthText.text = "非常强"; b.tvStrengthText.setTextColor(Color.parseColor("#2196F3")) }
        }
    }

    private fun showMessage(isSuccess: Boolean, text: String, bgColor: Int, textColor: Int) {
        b.layoutMessage.visibility = View.VISIBLE
        b.layoutMessage.background = null
        b.layoutMessage.background = GradientDrawable().apply { cornerRadius = 12f; setColor(bgColor) }
        b.ivMsgIcon.setImageResource(if (isSuccess) android.R.drawable.ic_menu_info_details else android.R.drawable.ic_dialog_alert)
        b.ivMsgIcon.setColorFilter(textColor)
        b.tvMsgText.text = text; b.tvMsgText.setTextColor(textColor)
    }

    private fun setBtnEnabled(enabled: Boolean) {
        b.btnSubmitPwd.isEnabled = enabled
        b.btnSubmitPwd.alpha = if (enabled) 1.0f else 0.5f
    }

    private fun doChangePassword() {
        val old = b.etOldPwd.text.toString()
        val new = b.etNewPwd.text.toString()
        val p = (application as ClassroomIoTApp).prefs

        setBtnEnabled(false)
        b.btnSubmitPwd.text = "修改中..."
        isShowingNetworkMsg = true // 锁定UI，防止点击按钮失去焦点把提示盖掉

        lifecycleScope.launch {
            try {
                val res = api.changePassword(p.username ?: "", old, new)
                if (res.success) {
                    b.layoutStrength.visibility = View.GONE
                    showMessage(true, "密码修改成功", Color.parseColor("#E8F5E9"), Color.parseColor("#388E3C"))
                    android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ finish() }, 1200)
                } else {
                    b.layoutStrength.visibility = View.GONE
                    showMessage(false, res.msg.ifBlank { "修改失败" }, Color.parseColor("#FFEBEE"), Color.RED)
                    b.btnSubmitPwd.text = "确认修改"
                }
            } catch (e: Exception) {
                b.layoutStrength.visibility = View.GONE
                showMessage(false, "网络请求失败", Color.parseColor("#FFEBEE"), Color.RED)
                b.btnSubmitPwd.text = "确认修改"
            }
        }
    }
}
