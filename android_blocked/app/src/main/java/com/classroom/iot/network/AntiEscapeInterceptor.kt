package com.classroom.iot.network

import okhttp3.Interceptor
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import java.net.URI

/**
 * 防逃逸拦截器：严禁跨域重定向
 */
class AntiEscapeInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val response = chain.proceed(originalRequest)

        if (response.isRedirect) {
            val locationUrl = response.header("Location")
            if (locationUrl != null) {
                try {
                    val newHost = URI(locationUrl).host
                    val oldHost = originalRequest.url.host

                    // 如果重定向的目标 IP 和你配置的服务器 IP 不一致，直接掐断返回 403！
                    if (newHost != oldHost) {
                        return response.newBuilder()
                            .body("Blocked".toResponseBody())
                            .code(403)
                            .message("Forbidden Redirect")
                            .build()
                    }
                } catch (e: Exception) {
                    return response.newBuilder()
                        .body("Blocked".toResponseBody())
                        .code(403)
                        .build()
                }
            }
        }
        return response
    }
}
