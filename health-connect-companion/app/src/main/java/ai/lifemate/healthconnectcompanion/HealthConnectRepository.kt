package ai.lifemate.healthconnectcompanion

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.HealthConnectFeatures
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Duration
import java.time.Instant
import kotlin.reflect.KClass

data class LatestHeartRate(
    val bpm: Long,
    val measuredAt: Instant,
)

class HealthConnectRepository(private val context: Context) {
    private val client by lazy { HealthConnectClient.getOrCreate(context) }

    val requiredPermissions: Set<String> =
        setOf(HealthPermission.getReadPermission(HeartRateRecord::class))

    fun sdkStatus(): Int =
        HealthConnectClient.getSdkStatus(context, PROVIDER_PACKAGE_NAME)

    suspend fun grantedPermissions(): Set<String> =
        client.permissionController.getGrantedPermissions()

    fun isBackgroundReadAvailable(): Boolean =
        client.features.getFeatureStatus(
            HealthConnectFeatures.FEATURE_READ_HEALTH_DATA_IN_BACKGROUND,
        ) == HealthConnectFeatures.FEATURE_STATUS_AVAILABLE

    suspend fun readLatestHeartRate(
        lookback: Duration = Duration.ofHours(12),
    ): LatestHeartRate? {
        val now = Instant.now()
        val response =
            client.readRecords(
                ReadRecordsRequest(
                    recordType = HeartRateRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(now.minus(lookback), now),
                    ascendingOrder = false,
                    pageSize = 200,
                ),
            )

        return response.records
            .flatMap { record -> record.samples.map { sample -> sample.beatsPerMinute to sample.time } }
            .maxByOrNull { (_, measuredAt) -> measuredAt }
            ?.let { (bpm, measuredAt) -> LatestHeartRate(bpm = bpm.toLong(), measuredAt = measuredAt) }
    }

    companion object {
        const val PROVIDER_PACKAGE_NAME = "com.google.android.apps.healthdata"
    }
}
