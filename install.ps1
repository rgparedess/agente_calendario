# install.ps1 - Script de instalación manual para Windows (calendario_ics + agente_calendario)
# Copia los archivos .py a ~\.local\bin, crea wrappers .bat,
# añade el directorio al PATH (opcional) y configura CALENDARIO_ICS_DIR (opcional).

$ErrorActionPreference = "Stop"

# ------------------- Configuración -------------------
$InstallDir = "$env:USERPROFILE\.local\bin"
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

function Install-Script {
    param($src, $name)
    $dest = Join-Path $InstallDir $name
    Write-Host "Instalando $name en $dest..."
    Copy-Item -Path $src -Destination $dest -Force
    $bat = Join-Path $InstallDir "$name.bat"
    "@echo off`npython `"$dest`" %*" | Out-File -FilePath $bat -Encoding ASCII
}

# ------------------- Instalación de scripts -------------------
if (Test-Path "calendario_ics.py") {
    Install-Script "calendario_ics.py" "calendario_ics.py"
} else {
    Write-Host "[!] Advertencia: calendario_ics.py no encontrado."
}

if (Test-Path "agente_calendario.py") {
    Install-Script "agente_calendario.py" "calendario-agent"
} else {
    Write-Host "[!] Advertencia: agente_calendario.py no encontrado."
}

# ------------------- Añadir al PATH (opcional) -------------------
function Add-ToUserPath {
    param($Directory)
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$Directory*") {
        Write-Host "[?] ¿Deseas añadir $Directory al PATH de usuario para ejecutar los comandos desde cualquier terminal? (s/N)"
        $respuesta = Read-Host
        if ($respuesta -eq "s" -or $respuesta -eq "S") {
            $newPath = "$currentPath;$Directory"
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Write-Host "[INFO] Directorio añadido al PATH. Reinicia la terminal para que los cambios surtan efecto."
        } else {
            Write-Host "[INFO] Puedes añadirlo manualmente más tarde desde las variables de entorno del sistema."
        }
    } else {
        Write-Host "[INFO] El directorio ya está en el PATH."
    }
}

# ------------------- Configurar CALENDARIO_ICS_DIR (opcional) -------------------
function Set-CalendarDir {
    # Buscar la carpeta de Rainlendar (Windows)
    $userProfile = $env:USERPROFILE
    $rainlendarPaths = @(
        "$userProfile\.rainlendar2",
        "$userProfile\.rainlendar2\Calendar",
        "$userProfile\Documents\Rainlendar",
        "$userProfile\Documents\Rainlendar\Calendar"
    )
    $foundPath = $null
    foreach ($p in $rainlendarPaths) {
        if (Test-Path $p) {
            # Verificar si contiene archivos .ics
            $icsFiles = Get-ChildItem -Path $p -Filter "*.ics" -ErrorAction SilentlyContinue
            if ($icsFiles) {
                $foundPath = $p
                break
            }
        }
    }

    if ($foundPath) {
        Write-Host "[INFO] Se detectó la carpeta de Rainlendar en: $foundPath"
        Write-Host "[?] ¿Deseas configurar la variable de entorno CALENDARIO_ICS_DIR con esta ruta? (s/N)"
        $respuesta = Read-Host
        if ($respuesta -eq "s" -or $respuesta -eq "S") {
            [Environment]::SetEnvironmentVariable("CALENDARIO_ICS_DIR", $foundPath, "User")
            Write-Host "[INFO] Variable CALENDARIO_ICS_DIR configurada. Reinicia la terminal para que surta efecto."
        } else {
            Write-Host "[INFO] Puedes configurarla manualmente con `$env:CALENDARIO_ICS_DIR='ruta'"
        }
    } else {
        Write-Host "[INFO] No se detectó una carpeta de Rainlendar. Si usas otro calendario, configura CALENDARIO_ICS_DIR manualmente."
    }
}

# ------------------- Ejecutar configuraciones -------------------
Add-ToUserPath $InstallDir
Set-CalendarDir

Write-Host "[INFO] Instalación manual completada."
Write-Host "[INFO] Ahora puedes ejecutar 'calendario-cli' y 'calendario-agent' desde cualquier terminal (tras reiniciar si añadiste al PATH)."