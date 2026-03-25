"""API key configuration page"""
from PyQt6.QtWidgets import (
    QWizardPage,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QTextBrowser,
    QFormLayout,
)
from PyQt6.QtCore import Qt


class ApiKeyPage(QWizardPage):
    """Legacy page kept for compatibility with the current wizard flow."""

    def __init__(self):
        super().__init__()
        self.setTitle("Codex Login")
        self.setSubTitle("Codex CLI usually uses ChatGPT sign-in or an OpenAI API key")

        layout = QVBoxLayout()

        # Instructions
        instructions = QTextBrowser()
        instructions.setOpenExternalLinks(True)
        instructions.setMaximumHeight(150)
        instructions.setHtml(
            """
            <p>
                To use Codex CLI with Embodied Codex, sign in with ChatGPT or configure an OpenAI API key.
            </p>
            <ul>
                <li>Recommended: run <code>codex login</code> in a terminal before using the tools</li>
                <li>You can also configure an OpenAI API key separately if that is how you use Codex</li>
                <li>This installer does not need to store a Claude-specific API key</li>
            </ul>
            """
        )
        layout.addWidget(instructions)

        # API key input
        form_layout = QFormLayout()

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Optional: leave blank for codex login flow")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Optional note:", self.api_key_input)

        layout.addLayout(form_layout)

        # Note
        note = QLabel(
            "💡 Codex CLI stores its own auth separately.\n"
            "Nothing entered here is required for the embodied-codex repository itself."
        )
        note.setWordWrap(True)
        note.setStyleSheet("QLabel { color: #666; margin-top: 10px; }")
        layout.addWidget(note)

        layout.addStretch()
        self.setLayout(layout)

        # Register field (not required - user might skip)
        self.registerField("api_key", self.api_key_input)
