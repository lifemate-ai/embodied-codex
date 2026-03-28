package ai.lifemate.healthconnectcompanion

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.HealthConnectClient
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import java.time.Instant
import androidx.health.connect.client.permission.HealthPermission.Companion.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND

data class MainUiState(
    val endpointUrl: String = "",
    val bearerToken: String = "",
    val sdkStatus: Int = HealthConnectClient.SDK_UNAVAILABLE,
    val permissionsGranted: Boolean = false,
    val backgroundReadAvailable: Boolean = false,
    val backgroundReadGranted: Boolean = false,
    val autoSendEnabled: Boolean = false,
    val autoSendIntervalMinutes: Long = 15,
    val lastHeartRateBpm: Long? = null,
    val lastHeartRateAt: String? = null,
    val statusMessage: String = "Not started.",
    val busy: Boolean = false,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val prefs = CompanionPrefs(application)
    private val repository = HealthConnectRepository(application)
    private val initialSettings = prefs.load()

    var uiState by mutableStateOf(
        MainUiState(
            endpointUrl = initialSettings.endpointUrl,
            bearerToken = initialSettings.bearerToken,
            autoSendEnabled = initialSettings.autoSendEnabled,
            autoSendIntervalMinutes = initialSettings.autoSendIntervalMinutes,
        ),
    )
        private set

    val requiredPermissions: Set<String>
        get() = repository.requiredPermissions

    val backgroundPermissionRequest: Set<String>
        get() = setOf(PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND)

    init {
        refreshStatus()
    }

    fun setEndpointUrl(value: String) {
        uiState = uiState.copy(endpointUrl = value)
    }

    fun setBearerToken(value: String) {
        uiState = uiState.copy(bearerToken = value)
    }

    fun setAutoSendIntervalMinutes(value: Long) {
        uiState = uiState.copy(autoSendIntervalMinutes = value.coerceAtLeast(15L))
    }

    fun saveSettings() {
        prefs.save(
            CompanionSettings(
                endpointUrl = uiState.endpointUrl,
                bearerToken = uiState.bearerToken,
                autoSendEnabled = uiState.autoSendEnabled,
                autoSendIntervalMinutes = uiState.autoSendIntervalMinutes,
            ),
        )
        uiState = uiState.copy(statusMessage = "Saved settings.")
    }

    fun refreshStatus() {
        viewModelScope.launch {
            val sdkStatus = repository.sdkStatus()
            val backgroundReadAvailable =
                sdkStatus == HealthConnectClient.SDK_AVAILABLE &&
                    repository.isBackgroundReadAvailable()
            val permissionsGranted =
                if (sdkStatus == HealthConnectClient.SDK_AVAILABLE) {
                    repository.grantedPermissions().containsAll(repository.requiredPermissions)
                } else {
                    false
                }
            val backgroundReadGranted =
                if (sdkStatus == HealthConnectClient.SDK_AVAILABLE) {
                    repository.grantedPermissions().contains(PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND)
                } else {
                    false
                }

            uiState =
                uiState.copy(
                    sdkStatus = sdkStatus,
                    permissionsGranted = permissionsGranted,
                    backgroundReadAvailable = backgroundReadAvailable,
                    backgroundReadGranted = backgroundReadGranted,
                    statusMessage =
                        buildStatusMessage(
                            sdkStatus = sdkStatus,
                            permissionsGranted = permissionsGranted,
                            backgroundReadAvailable = backgroundReadAvailable,
                            backgroundReadGranted = backgroundReadGranted,
                        ),
                )
        }
    }

    fun previewLatestHeartRate() {
        viewModelScope.launch {
            uiState = uiState.copy(busy = true, statusMessage = "Reading latest heart rate...")
            val latest = repository.readLatestHeartRate()
            uiState =
                if (latest == null) {
                    uiState.copy(
                        busy = false,
                        lastHeartRateBpm = null,
                        lastHeartRateAt = null,
                        statusMessage = "No recent heart-rate samples found in Health Connect.",
                    )
                } else {
                    uiState.copy(
                        busy = false,
                        lastHeartRateBpm = latest.bpm,
                        lastHeartRateAt = latest.measuredAt.toString(),
                        statusMessage = "Loaded latest heart rate from Health Connect.",
                    )
                }
        }
    }

    fun sendLatestHeartRate() {
        viewModelScope.launch {
            prefs.save(
                CompanionSettings(
                    endpointUrl = uiState.endpointUrl,
                    bearerToken = uiState.bearerToken,
                ),
            )
            uiState = uiState.copy(busy = true, statusMessage = "Sending latest heart rate...")

            val latest = repository.readLatestHeartRate()
            if (latest == null) {
                uiState =
                    uiState.copy(
                        busy = false,
                        statusMessage = "No heart-rate sample available to send.",
                    )
                return@launch
            }

            val result =
                BiometricsSender.send(
                    endpointUrl = uiState.endpointUrl.trim(),
                    bearerToken = uiState.bearerToken.trim(),
                    payload =
                        CompanionBiometricsPayload(
                            source = "health-connect",
                            updatedAt = Instant.now(),
                            heartRateBpm = latest.bpm,
                            heartRateMeasuredAt = latest.measuredAt,
                        ),
                )

            uiState =
                result.fold(
                    onSuccess = {
                        uiState.copy(
                            busy = false,
                            lastHeartRateBpm = latest.bpm,
                            lastHeartRateAt = latest.measuredAt.toString(),
                            statusMessage = "Sent latest heart rate to embodied-codex.",
                        )
                    },
                    onFailure = { error ->
                        uiState.copy(
                            busy = false,
                            lastHeartRateBpm = latest.bpm,
                            lastHeartRateAt = latest.measuredAt.toString(),
                            statusMessage = "Send failed: ${error.message}",
                        )
                    },
                )
        }
    }

    fun enableAutoSend() {
        prefs.save(
            CompanionSettings(
                endpointUrl = uiState.endpointUrl,
                bearerToken = uiState.bearerToken,
                autoSendEnabled = true,
                autoSendIntervalMinutes = uiState.autoSendIntervalMinutes,
            ),
        )
        PeriodicSendWorker.schedule(
            getApplication(),
            uiState.autoSendIntervalMinutes,
        )
        uiState =
            uiState.copy(
                autoSendEnabled = true,
                statusMessage =
                    "Scheduled periodic send every ${uiState.autoSendIntervalMinutes} minutes.",
            )
    }

    fun disableAutoSend() {
        prefs.save(
            CompanionSettings(
                endpointUrl = uiState.endpointUrl,
                bearerToken = uiState.bearerToken,
                autoSendEnabled = false,
                autoSendIntervalMinutes = uiState.autoSendIntervalMinutes,
            ),
        )
        PeriodicSendWorker.cancel(getApplication())
        uiState =
            uiState.copy(
                autoSendEnabled = false,
                statusMessage = "Periodic send disabled.",
            )
    }

    private fun buildStatusMessage(
        sdkStatus: Int,
        permissionsGranted: Boolean,
        backgroundReadAvailable: Boolean,
        backgroundReadGranted: Boolean,
    ): String =
        when (sdkStatus) {
            HealthConnectClient.SDK_UNAVAILABLE ->
                "Health Connect is unavailable on this device."

            HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED ->
                "Health Connect provider needs installation or update."

            HealthConnectClient.SDK_AVAILABLE ->
                if (permissionsGranted) {
                    if (backgroundReadAvailable && !backgroundReadGranted) {
                        "Health Connect foreground read is ready. Grant background access for periodic send."
                    } else {
                        "Health Connect ready."
                    }
                } else {
                    "Grant Health Connect heart-rate permission."
                }

            else -> "Health Connect status: $sdkStatus"
        }
}

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    private val permissionsLauncher =
        registerForActivityResult(PermissionController.createRequestPermissionResultContract()) {
            viewModel.refreshStatus()
        }

    private val backgroundPermissionsLauncher =
        registerForActivityResult(PermissionController.createRequestPermissionResultContract()) {
            viewModel.refreshStatus()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val state = viewModel.uiState

            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Column(
                        modifier =
                            Modifier
                                .fillMaxSize()
                                .verticalScroll(rememberScrollState())
                                .padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        Text("Health Connect Companion", style = MaterialTheme.typography.headlineSmall)
                        Text(
                            "Reads the latest Health Connect heart-rate sample and sends it to embodied-codex.",
                            style = MaterialTheme.typography.bodyMedium,
                        )

                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Text("Status", style = MaterialTheme.typography.titleMedium)
                                Text(state.statusMessage)
                                Text("SDK status: ${state.sdkStatus}")
                                Text("Permission granted: ${state.permissionsGranted}")
                                Text("Background read available: ${state.backgroundReadAvailable}")
                                Text("Background read granted: ${state.backgroundReadGranted}")
                                Text("Auto-send enabled: ${state.autoSendEnabled}")
                                Text("Auto-send interval: ${state.autoSendIntervalMinutes} min")
                                Text("Latest BPM: ${state.lastHeartRateBpm ?: "unknown"}")
                                Text("Measured at: ${state.lastHeartRateAt ?: "unknown"}")
                            }
                        }

                        OutlinedTextField(
                            value = state.endpointUrl,
                            onValueChange = viewModel::setEndpointUrl,
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Endpoint URL") },
                            singleLine = true,
                        )

                        OutlinedTextField(
                            value = state.bearerToken,
                            onValueChange = viewModel::setBearerToken,
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Bearer token (optional)") },
                            singleLine = true,
                        )

                        Text("Auto-send interval", style = MaterialTheme.typography.titleMedium)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            listOf(15L, 30L, 60L).forEach { interval ->
                                FilterChip(
                                    selected = state.autoSendIntervalMinutes == interval,
                                    onClick = { viewModel.setAutoSendIntervalMinutes(interval) },
                                    label = { Text("${interval}m") },
                                )
                            }
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(onClick = viewModel::saveSettings) {
                                Text("Save")
                            }
                            Button(onClick = viewModel::refreshStatus) {
                                Text("Refresh")
                            }
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(
                                onClick = {
                                    permissionsLauncher.launch(viewModel.requiredPermissions)
                                },
                            ) {
                                Text("Grant permission")
                            }
                            Button(
                                onClick = {
                                    backgroundPermissionsLauncher.launch(viewModel.backgroundPermissionRequest)
                                },
                                enabled = state.backgroundReadAvailable,
                            ) {
                                Text("Grant background")
                            }
                            Button(
                                onClick = viewModel::previewLatestHeartRate,
                                enabled = !state.busy,
                            ) {
                                Text("Preview latest HR")
                            }
                        }

                        Button(
                            onClick = viewModel::sendLatestHeartRate,
                            enabled = !state.busy && state.endpointUrl.isNotBlank(),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(if (state.busy) "Working..." else "Send to embodied-codex")
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(
                                onClick = viewModel::enableAutoSend,
                                enabled =
                                    !state.busy &&
                                        state.endpointUrl.isNotBlank() &&
                                        state.permissionsGranted &&
                                        (!state.backgroundReadAvailable || state.backgroundReadGranted),
                            ) {
                                Text("Enable periodic send")
                            }
                            Button(
                                onClick = viewModel::disableAutoSend,
                                enabled = state.autoSendEnabled,
                            ) {
                                Text("Disable periodic send")
                            }
                        }
                    }
                }
            }
        }
    }
}
