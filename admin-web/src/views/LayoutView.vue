<template>
  <div class="cs-page">
    <div class="cs-header">
      <div><b>Close Shot 后台（MVP）</b></div>
      <div><el-button @click="logout">退出</el-button></div>
    </div>

    <el-menu mode="horizontal" router :default-active="$route.path" style="margin-bottom: 16px">
      <el-menu-item :index="withAdminWebBase('/studio/upload')">新增</el-menu-item>
      <el-menu-item :index="withAdminWebBase('/admin/certifications')">认证审核</el-menu-item>
      <el-menu-item :index="withAdminWebBase('/admin/analytics')">埋点分析</el-menu-item>
      <el-menu-item :index="withAdminWebBase('/admin/user-portraits')">用户画像</el-menu-item>
      <el-menu-item :index="withAdminWebBase('/admin/db')">数据库浏览</el-menu-item>
      <el-menu-item :index="withAdminWebBase('/admin/operation-logs')">操作日志</el-menu-item>
      <el-menu-item :index="withAdminWebBase('/seed')">开发 Seed</el-menu-item>
    </el-menu>

    <div class="cs-hint">
      提示：如果要让小程序也能显示图片，建议使用后端代理地址 <code>/media/*</code>（上传接口会返回 <code>proxy_url</code>）。
    </div>
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from "../stores/auth";
import { router } from "../router";
import { ADMIN_LOGIN_PATH, withAdminWebBase } from "../lib/adminSecurity";

const auth = useAuthStore();
function logout() {
  auth.logout();
  router.push(ADMIN_LOGIN_PATH);
}
</script>

