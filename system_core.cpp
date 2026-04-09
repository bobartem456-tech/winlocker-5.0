// system_core.cpp
// DLL для системных вызовов Windows с экспортируемыми функциями

#include <windows.h>
#include <tlhelp32.h>
#include <psapi.h>
#include <string>
#include <vector>
#include <algorithm>

// Макрос для экспорта функций
#ifdef __cplusplus
extern "C" {
#endif

// ==================== ОСНОВНЫЕ СИСТЕМНЫЕ ФУНКЦИИ ====================

__declspec(dllexport) int lock_workstation() {
    // Блокировка рабочей станции
    return LockWorkStation() ? 1 : 0;
}

__declspec(dllexport) int shutdown_system(int force) {
    // Выключение компьютера
    HANDLE hToken;
    TOKEN_PRIVILEGES tkp;
    
    // Получаем токен текущего процесса
    if (!OpenProcessToken(GetCurrentProcess(), 
                         TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &hToken)) {
        return 0;
    }
    
    // Получаем LUID для привилегии выключения
    LookupPrivilegeValue(NULL, SE_SHUTDOWN_NAME, &tkp.Privileges[0].Luid);
    
    tkp.PrivilegeCount = 1;
    tkp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;
    
    // Включаем привилегию
    AdjustTokenPrivileges(hToken, FALSE, &tkp, 0, NULL, 0);
    
    // Выполняем выключение
    DWORD flags = EWX_SHUTDOWN | EWX_FORCE;
    if (force) {
        flags |= EWX_FORCEIFHUNG;
    }
    
    int result = ExitWindowsEx(flags, SHTDN_REASON_MAJOR_OTHER);
    CloseHandle(hToken);
    
    return result ? 1 : 0;
}

__declspec(dllexport) int reboot_system(int force) {
    // Перезагрузка компьютера
    HANDLE hToken;
    TOKEN_PRIVILEGES tkp;
    
    if (!OpenProcessToken(GetCurrentProcess(), 
                         TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &hToken)) {
        return 0;
    }
    
    LookupPrivilegeValue(NULL, SE_SHUTDOWN_NAME, &tkp.Privileges[0].Luid);
    tkp.PrivilegeCount = 1;
    tkp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;
    
    AdjustTokenPrivileges(hToken, FALSE, &tkp, 0, NULL, 0);
    
    DWORD flags = EWX_REBOOT | EWX_FORCE;
    if (force) {
        flags |= EWX_FORCEIFHUNG;
    }
    
    int result = ExitWindowsEx(flags, SHTDN_REASON_MAJOR_OTHER);
    CloseHandle(hToken);
    
    return result ? 1 : 0;
}

// ==================== УПРАВЛЕНИЕ ПРОЦЕССАМИ ====================

__declspec(dllexport) int kill_process_by_name(const char* process_name) {
    // Завершение процесса по имени
    DWORD processes[1024], needed;
    if (!EnumProcesses(processes, sizeof(processes), &needed)) {
        return 0;
    }
    
    int process_count = needed / sizeof(DWORD);
    int killed = 0;
    
    for (int i = 0; i < process_count; i++) {
        if (processes[i] == 0) continue;
        
        HANDLE hProcess = OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION, 
                                     FALSE, processes[i]);
        if (hProcess) {
            char name[MAX_PATH] = {0};
            if (GetModuleBaseNameA(hProcess, NULL, name, sizeof(name))) {
                if (_stricmp(name, process_name) == 0) {
                    if (TerminateProcess(hProcess, 0)) {
                        killed++;
                    }
                }
            }
            CloseHandle(hProcess);
        }
    }
    
    return killed;
}

__declspec(dllexport) int kill_process_by_id(DWORD pid) {
    // Завершение процесса по ID
    HANDLE hProcess = OpenProcess(PROCESS_TERMINATE, FALSE, pid);
    if (!hProcess) {
        return 0;
    }
    
    int result = TerminateProcess(hProcess, 0) ? 1 : 0;
    CloseHandle(hProcess);
    
    return result;
}

__declspec(dllexport) char* get_process_list() {
    // Получение списка процессов
    DWORD processes[1024], needed;
    if (!EnumProcesses(processes, sizeof(processes), &needed)) {
        return nullptr;
    }
    
    int process_count = needed / sizeof(DWORD);
    std::string result;
    
    for (int i = 0; i < process_count; i++) {
        if (processes[i] == 0) continue;
        
        HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                                     FALSE, processes[i]);
        if (hProcess) {
            char name[MAX_PATH] = {0};
            if (GetModuleBaseNameA(hProcess, NULL, name, sizeof(name))) {
                result += std::to_string(processes[i]) + ":" + name + "\n";
            }
            CloseHandle(hProcess);
        }
    }
    
    char* buffer = new char[result.size() + 1];
    strcpy_s(buffer, result.size() + 1, result.c_str());
    return buffer;
}

// ==================== УПРАВЛЕНИЕ ОКНАМИ ====================

__declspec(dllexport) int hide_window_by_title(const char* window_title) {
    // Скрытие окна по заголовку
    HWND hWnd = FindWindowA(NULL, window_title);
    if (!hWnd) {
        return 0;
    }
    
    return ShowWindow(hWnd, SW_HIDE) ? 1 : 0;
}

__declspec(dllexport) int show_window_by_title(const char* window_title) {
    // Показать окно по заголовку
    HWND hWnd = FindWindowA(NULL, window_title);
    if (!hWnd) {
        return 0;
    }
    
    return ShowWindow(hWnd, SW_SHOW) ? 1 : 0;
}

__declspec(dllexport) int minimize_all_windows() {
    // Свернуть все окна (Win+D)
    keybd_event(VK_LWIN, 0, 0, 0);
    keybd_event('D', 0, 0, 0);
    keybd_event('D', 0, KEYEVENTF_KEYUP, 0);
    keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0);
    return 1;
}

__declspec(dllexport) char* get_active_window_title() {
    // Получение заголовка активного окна
    HWND hWnd = GetForegroundWindow();
    if (!hWnd) {
        return nullptr;
    }
    
    char title[256] = {0};
    GetWindowTextA(hWnd, title, sizeof(title));
    
    char* buffer = new char[strlen(title) + 1];
    strcpy_s(buffer, strlen(title) + 1, title);
    return buffer;
}

// ==================== СИСТЕМНАЯ ИНФОРМАЦИЯ ====================

__declspec(dllexport) char* get_system_info_string() {
    // Получение системной информации в виде строки
    SYSTEM_INFO sysInfo;
    GetSystemInfo(&sysInfo);
    
    MEMORYSTATUSEX memoryStatus;
    memoryStatus.dwLength = sizeof(memoryStatus);
    GlobalMemoryStatusEx(&memoryStatus);
    
    char computerName[MAX_COMPUTERNAME_LENGTH + 1];
    DWORD size = sizeof(computerName);
    GetComputerNameA(computerName, &size);
    
    char userName[256];
    DWORD userNameSize = sizeof(userName);
    GetUserNameA(userName, &userNameSize);
    
    std::string info = "Computer: " + std::string(computerName) + "\n";
    info += "User: " + std::string(userName) + "\n";
    info += "CPU Cores: " + std::to_string(sysInfo.dwNumberOfProcessors) + "\n";
    info += "RAM Total: " + std::to_string(memoryStatus.ullTotalPhys / (1024 * 1024)) + " MB\n";
    info += "RAM Available: " + std::to_string(memoryStatus.ullAvailPhys / (1024 * 1024)) + " MB\n";
    
    char* buffer = new char[info.size() + 1];
    strcpy_s(buffer, info.size() + 1, info.c_str());
    return buffer;
}

// ==================== УПРАВЛЕНИЕ ГРОМКОСТЬЮ ====================

__declspec(dllexport) int set_system_volume(int level) {
    // Установка уровня громкости (0-100)
    // Используем Windows Core Audio API через командную строку
    // Это упрощенная реализация
    if (level < 0) level = 0;
    if (level > 100) level = 100;
    
    char cmd[256];
    sprintf_s(cmd, "nircmd.exe setsysvolume %d", level * 655);
    
    STARTUPINFOA si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);
    
    if (CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, 1000);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return 1;
    }
    
    return 0;
}

__declspec(dllexport) int mute_system_volume() {
    // Отключение звука
    char cmd[] = "nircmd.exe mutesysvolume 1";
    
    STARTUPINFOA si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);
    
    if (CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, 1000);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return 1;
    }
    
    return 0;
}

__declspec(dllexport) int unmute_system_volume() {
    // Включение звука
    char cmd[] = "nircmd.exe mutesysvolume 0";
    
    STARTUPINFOA si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);
    
    if (CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, 1000);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return 1;
    }
    
    return 0;
}

// ==================== УТИЛИТНЫЕ ФУНКЦИИ ====================

__declspec(dllexport) void free_string(char* str) {
    // Освобождение памяти, выделенной в DLL
    if (str) {
        delete[] str;
    }
}

__declspec(dllexport) int execute_command(const char* command) {
    // Выполнение команды CMD
    STARTUPINFOA si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    
    // Создаем командную строку
    char cmd[1024];
    sprintf_s(cmd, "cmd.exe /c %s", command);
    
    if (CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        
        DWORD exitCode;
        GetExitCodeProcess(pi.hProcess, &exitCode);
        
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        
        return exitCode == 0 ? 1 : 0;
    }
    
    return 0;
}

__declspec(dllexport) int create_hidden_process(const char* exe_path, const char* args) {
    // Создание скрытого процесса
    STARTUPINFOA si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    
    char command_line[1024];
    if (args && strlen(args) > 0) {
        sprintf_s(command_line, "\"%s\" %s", exe_path, args);
    } else {
        sprintf_s(command_line, "\"%s\"", exe_path);
    }
    
    if (CreateProcessA(NULL, command_line, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW | DETACHED_PROCESS, 
                      NULL, NULL, &si, &pi)) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return 1;
    }
    
    return 0;
}

#ifdef __cplusplus
}
#endif

// ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    // Точка входа DLL
    switch (ul_reason_for_call) {
        case DLL_PROCESS_ATTACH:
        case DLL_THREAD_ATTACH:
        case DLL_THREAD_DETACH:
        case DLL_PROCESS_DETACH:
            break;
    }
    return TRUE;
}