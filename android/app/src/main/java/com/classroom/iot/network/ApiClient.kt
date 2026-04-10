package com.classroom.iot.network

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import com.classroom.iot.model.*
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import java.io.IOException
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

// 【关键修复1】增加 token 参数，但给个默认值，这样原有的 LoginActivity 不用改任何代码
class ApiClient(private val baseUrl: String, private val token: String = "") {
    private val gson = Gson()
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    suspend fun login(u: String, p: String): LoginResponse =
        post("/api/auth/login", """{"username":"$u","password_hash":"$p"}""".toRequestBody(JSON), LoginResponse::class.java)

    suspend fun getServerInfo(): ServerInfoResponse =
        get("/api/server/info", ServerInfoResponse::class.java)

    suspend fun getDates(): DateListResponse =
        get("/api/dates", DateListResponse::class.java)

    suspend fun getCourses(d: String): CourseListResponse =
        get("/api/dates/$d/courses", CourseListResponse::class.java)

    suspend fun getImages(d: String, i: Int, t: String): ImageListResponse =
        get("/api/dates/$d/courses/$i/$t/images", ImageListResponse::class.java)

    suspend fun getImageCount(d: String, i: Int, t: String): CountResponse =
        get("/api/dates/$d/courses/$i/$t/count", CountResponse::class.java)

    fun getImageUrl(d: String, i: Int, t: String, f: String): String =
        "$baseUrl/resource/$t/$d/$i/$f"

    suspend fun isReachable(): Boolean = try {
        getServerInfo(); true
    } catch(e: Exception) { false }

    // 【关键修复2】如果传了 token，则在请求头中带上
    private suspend fun <T> get(p: String, c: Class<T>): T = withContext(Dispatchers.IO) {
        val requestBuilder = Request.Builder().url("$baseUrl$p")
        if (token.isNotEmpty()) {
            requestBuilder.addHeader("Authorization", "Bearer $token")
        }
        parse(client.newCall(requestBuilder.build()).execute(), c)
    }

    private suspend fun <T> post(p: String, b: RequestBody, c: Class<T>): T = withContext(Dispatchers.IO) {
        val requestBuilder = Request.Builder().url("$baseUrl$p").post(b)
        if (token.isNotEmpty()) {
            requestBuilder.addHeader("Authorization", "Bearer $token")
        }
        parse(client.newCall(requestBuilder.build()).execute(), c)
    }

    private fun <T> parse(r: Response, c: Class<T>): T =
        gson.fromJson(r.body?.string() ?: throw IOException(), c)

    suspend fun changePassword(username: String, oldPwd: String, newPwd: String): ChangePwdResponse = withContext(Dispatchers.IO) {
        val sha256 = { s: String -> MessageDigest.getInstance("SHA-256").digest(s.toByteArray()).joinToString("") { "%02x".format(it) } }
        val json = """{"username":"$username", "old_password":"${sha256(oldPwd)}", "new_password":"${sha256(newPwd)}"}"""
        val body = json.toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("$baseUrl/api/change_password")
            .addHeader("Authorization", "Bearer $token") // 改密码也需要 token
            .post(body).build()
        val response = client.newCall(request).execute()
        val resStr = response.body?.string() ?: throw Exception("空响应")
        Gson().fromJson(resStr, ChangePwdResponse::class.java)
    }

    companion object {
        val JSON = "application/json; charset=utf-8".toMediaType()
    }
}

data class ChangePwdResponse(val success: Boolean, val msg: String = "")
