package com.classroom.iot.model
data class ServerInfo(val name: String, val ip: String, val port: Int) {
    val baseUrl: String get() = "http://$ip:$port"
}
