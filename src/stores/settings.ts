import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const darkMode = ref(localStorage.getItem('darkMode') !== 'false')
  const autoRefresh = ref(localStorage.getItem('autoRefresh') !== 'false')
  const refreshInterval = ref(Number(localStorage.getItem('refreshInterval')) || 30)
  const enableNotification = ref(localStorage.getItem('enableNotification') !== 'false')
  const warningThreshold = ref(Number(localStorage.getItem('warningThreshold')) || 80)
  const dangerThreshold = ref(Number(localStorage.getItem('dangerThreshold')) || 95)

  // 监听深色模式变化并应用
  watch(darkMode, (val) => {
    localStorage.setItem('darkMode', String(val))
    applyTheme(val)
  }, { immediate: true })

  // 应用主题
  function applyTheme(isDark: boolean) {
    const html = document.documentElement
    if (isDark) {
      html.classList.remove('light-theme')
      html.classList.add('dark-theme')
      html.classList.add('dark') // Element Plus 兼容
    } else {
      html.classList.remove('dark-theme')
      html.classList.remove('dark') // Element Plus 兼容
      html.classList.add('light-theme')
    }
  }

  function saveToLocal() {
    localStorage.setItem('autoRefresh', String(autoRefresh.value))
    localStorage.setItem('refreshInterval', String(refreshInterval.value))
    localStorage.setItem('enableNotification', String(enableNotification.value))
    localStorage.setItem('warningThreshold', String(warningThreshold.value))
    localStorage.setItem('dangerThreshold', String(dangerThreshold.value))
  }

  return {
    darkMode,
    autoRefresh,
    refreshInterval,
    enableNotification,
    warningThreshold,
    dangerThreshold,
    applyTheme,
    saveToLocal
  }
})
