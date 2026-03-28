package ai.lifemate.healthconnectcompanion

import android.content.Context

data class CompanionSettings(
    val endpointUrl: String = "http://192.168.1.198:8765/ingest",
    val bearerToken: String = "",
    val autoSendEnabled: Boolean = false,
    val autoSendIntervalMinutes: Long = 15,
)

class CompanionPrefs(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun load(): CompanionSettings =
        CompanionSettings(
            endpointUrl = prefs.getString(KEY_ENDPOINT_URL, DEFAULT_ENDPOINT_URL).orEmpty(),
            bearerToken = prefs.getString(KEY_BEARER_TOKEN, "").orEmpty(),
            autoSendEnabled = prefs.getBoolean(KEY_AUTO_SEND_ENABLED, false),
            autoSendIntervalMinutes = prefs.getLong(KEY_AUTO_SEND_INTERVAL_MINUTES, 15L),
        )

    fun save(settings: CompanionSettings) {
        prefs
            .edit()
            .putString(KEY_ENDPOINT_URL, settings.endpointUrl.trim())
            .putString(KEY_BEARER_TOKEN, settings.bearerToken.trim())
            .putBoolean(KEY_AUTO_SEND_ENABLED, settings.autoSendEnabled)
            .putLong(
                KEY_AUTO_SEND_INTERVAL_MINUTES,
                settings.autoSendIntervalMinutes.coerceAtLeast(15L),
            )
            .apply()
    }

    private companion object {
        const val PREFS_NAME = "health_connect_companion"
        const val KEY_ENDPOINT_URL = "endpoint_url"
        const val KEY_BEARER_TOKEN = "bearer_token"
        const val KEY_AUTO_SEND_ENABLED = "auto_send_enabled"
        const val KEY_AUTO_SEND_INTERVAL_MINUTES = "auto_send_interval_minutes"
        const val DEFAULT_ENDPOINT_URL = "http://192.168.1.198:8765/ingest"
    }
}
