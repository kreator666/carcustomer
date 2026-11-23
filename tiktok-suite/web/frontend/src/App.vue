<template>
  <el-container class="layout">
    <!-- 深色侧边栏 -->
    <el-aside width="220px" class="aside">
      <div class="logo">TikTok 线索工作台</div>
      <el-menu :default-active="$route.path" router background-color="#1d2b45" text-color="#c0c6d0"
        active-text-color="#ffd04b">
        <el-menu-item index="/leads"><el-icon><User /></el-icon><span>线索列表</span></el-menu-item>
        <el-menu-item index="/interactions"><el-icon><ChatDotRound /></el-icon><span>互动日志</span></el-menu-item>
        <el-menu-item index="/videos"><el-icon><VideoCamera /></el-icon><span>视频管理</span></el-menu-item>
        <el-menu-item index="/stats"><el-icon><DataAnalysis /></el-icon><span>数据统计</span></el-menu-item>
        <el-menu-item index="/templates"><el-icon><Document /></el-icon><span>话术模板</span></el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon><span>设置</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">{{ $route.meta.title }}</span>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style>
html, body, #app { height: 100%; margin: 0; }
.layout { height: 100%; }
.aside { background-color: #1d2b45; }
.logo { color: #fff; font-size: 16px; font-weight: 600; text-align: center; padding: 18px 0; border-bottom: 1px solid #2b3d5e; }
.aside .el-menu { border-right: none; }
.header { background: #fff; border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; }
.header .title { font-size: 16px; font-weight: 600; }
.main { background: #f5f7fa; }
</style>
