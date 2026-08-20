# Instalador para calendario-agent (ejecutable empaquetado con PyInstaller)
# Ejecutar como Administrador para añadir al PATH del sistema (opcional)

$ErrorActionPreference = "Stop"

$InstallDir = "$env:ProgramFiles\calendario_agent"
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

if (Test-Path ".\calendario-agent.exe") {
    Copy-Item ".\calendario-agent.exe" -Destination "$InstallDir\calendario-agent.exe" -Force
    Write-Host "[INFO] Ejecutable copiado a $InstallDir\calendario-agent.exe"
} else {
    Write-Host "[ERROR] No se encuentra 'calendario-agent.exe'."
    exit 1
}

function Add-ToUserPath {
    param($Directory)
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$Directory*") {
        Write-Host "[?] ¿Deseas añadir $Directory al PATH de usuario? (s/N)"
        $respuesta = Read-Host
        if ($respuesta -eq "s" -or $respuesta -eq "S") {
            $newPath = "$currentPath;$Directory"
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Write-Host "[INFO] Directorio añadido al PATH de usuario."
            Write-Host "[*] Reinicia la terminal para que los cambios surtan efecto."
        } else {
            Write-Host "[INFO]  Puedes añadirlo manualmente desde las variables de entorno."
        }
    } else {
        Write-Host "[INFO]  El directorio ya está en el PATH de usuario."
    }
}

Add-ToUserPath $InstallDir

Write-Host ""
Write-Host "[INFO] Instalación completada."
Write-Host "   Ahora puedes ejecutar: calendario-agent --host 127.0.0.1 --port 8082"