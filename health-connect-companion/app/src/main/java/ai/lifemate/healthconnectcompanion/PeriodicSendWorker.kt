package ai.lifemate.healthconnectcompanion

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.time.Duration
import java.time.Instant
import java.util.concurrent.TimeUnit

class PeriodicSendWorker(
    appContext: Context,
    workerParams: WorkerParameters,
) : CoroutineWorker(appContext, workerParams) {
    override suspend fun doWork(): Result {
        val prefs = CompanionPrefs(applicationContext)
        val settings = prefs.load()
        if (!settings.autoSendEnabled) {
            return Result.success()
        }

        val repository = HealthConnectRepository(applicationContext)
        val latest =
            runCatching { repository.readLatestHeartRate() }.getOrElse {
                return Result.retry()
            }
        if (latest == null) {
            return Result.success()
        }

        return BiometricsSender.send(
            endpointUrl = settings.endpointUrl,
            bearerToken = settings.bearerToken,
            payload =
                CompanionBiometricsPayload(
                    source = "health-connect",
                    updatedAt = Instant.now(),
                    heartRateBpm = latest.bpm,
                    heartRateMeasuredAt = latest.measuredAt,
                ),
        ).fold(
            onSuccess = { Result.success() },
            onFailure = { Result.retry() },
        )
    }

    companion object {
        const val UNIQUE_WORK_NAME = "health-connect-periodic-send"

        fun schedule(context: Context, intervalMinutes: Long) {
            val request =
                PeriodicWorkRequestBuilder<PeriodicSendWorker>(
                    intervalMinutes.coerceAtLeast(15L),
                    TimeUnit.MINUTES,
                ).setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build(),
                ).build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                UNIQUE_WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(UNIQUE_WORK_NAME)
        }
    }
}
