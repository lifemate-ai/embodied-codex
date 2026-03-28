package ai.lifemate.healthconnectcompanion

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant

data class CompanionBiometricsPayload(
    val source: String = "health-connect",
    val updatedAt: Instant = Instant.now(),
    val heartRateBpm: Long?,
    val heartRateMeasuredAt: Instant?,
    val restingHeartRateBpm: Long? = null,
    val sleepScore: Long? = null,
    val sleepMeasuredAt: Instant? = null,
    val bodyBattery: Long? = null,
    val bodyBatteryMeasuredAt: Instant? = null,
)

object BiometricsSender {
    suspend fun send(
        endpointUrl: String,
        bearerToken: String,
        payload: CompanionBiometricsPayload,
    ): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                val connection = (URL(endpointUrl).openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    doOutput = true
                    connectTimeout = 10_000
                    readTimeout = 10_000
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    if (bearerToken.isNotBlank()) {
                        setRequestProperty("Authorization", "Bearer ${bearerToken.trim()}")
                    }
                }

                val body =
                    JSONObject()
                        .put("source", payload.source)
                        .put("updated_at", payload.updatedAt.toString())
                        .put("heart_rate_bpm", payload.heartRateBpm)
                        .put("heart_rate_measured_at", payload.heartRateMeasuredAt?.toString())
                        .put("resting_heart_rate_bpm", payload.restingHeartRateBpm)
                        .put("sleep_score", payload.sleepScore)
                        .put("sleep_measured_at", payload.sleepMeasuredAt?.toString())
                        .put("body_battery", payload.bodyBattery)
                        .put("body_battery_measured_at", payload.bodyBatteryMeasuredAt?.toString())
                        .toString()

                BufferedOutputStream(connection.outputStream).use { output ->
                    output.write(body.toByteArray(Charsets.UTF_8))
                    output.flush()
                }

                val code = connection.responseCode
                if (code !in 200..299) {
                    error("POST failed with HTTP $code")
                }
            }
        }
}

