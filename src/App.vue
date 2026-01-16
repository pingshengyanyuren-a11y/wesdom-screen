<!--
  组件名: App.vue
  功能: 根组件
-->
<script setup lang="ts">
// 根组件仅负责渲染路由视图
import SmartAgent from '@/components/SmartAgent.vue'
</script>

<template>
  <router-view />
  <SmartAgent style="position: fixed; z-index: 99999;" />
</template>

<style>
/* 全局样式已在 water-theme.css 中定义 */
</style>
