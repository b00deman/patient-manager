' تشغيل برنامج تسجيل المرضى
' يبدأ المخدم في الخلفية ويفتح المتصفح تلقائياً
Set objShell = CreateObject("WScript.Shell")
strDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
strPython = objShell.ExpandEnvironmentStrings("%PYTHON_PATH%")
If strPython = "%PYTHON_PATH%" Then
    strPython = "python"
End If
objShell.Run strPython & " """ & strDir & "\server.py""", 0, False
