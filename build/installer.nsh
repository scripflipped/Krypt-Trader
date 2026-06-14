; Krypt Trader NSIS installer add-ons.
; Loaded by electron-builder (see package.json -> build.nsis.include).

!macro customInstall
  ; Add an exclusion to the install dir so Windows Defender doesn't
  ; quarantine the bundled Python backend on first launch. This is a
  ; best-effort PowerShell call — silently no-op if it fails.
  nsExec::ExecToLog 'powershell -NoProfile -Command "try { Add-MpPreference -ExclusionPath $InstDir -ErrorAction Stop } catch {}"'
!macroend

!macro customUnInstall
  ; Don't delete user data on uninstall — they keep their settings,
  ; profiles, credentials, and DB if they reinstall later. The user
  ; can clear via "Delete saved keys" in the API page first.
!macroend
