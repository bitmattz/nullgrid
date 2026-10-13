import QtQuick

// Text in the UI font. `label` makes it a small, dim, letter-spaced caption.
Text {
    property bool label: false
    property bool mono: false
    color: label ? Theme.dim : Theme.text
    font.family: mono ? Theme.fontMono : Theme.fontUi
    font.pixelSize: label ? Math.round(Theme.fontSize * 0.8) : Theme.fontSize
    font.letterSpacing: label ? 1.5 : 0
    font.weight: label ? Font.DemiBold : Font.Medium
    font.capitalization: label ? Font.AllUppercase : Font.MixedCase
    elide: Text.ElideRight
    verticalAlignment: Text.AlignVCenter
}
