<template>
  <div class="cs-page">
    <div class="cs-header">
      <div><b>Close Shot 后台（MVP）</b></div>
      <div style="display: flex; align-items: center; gap: 12px">
        <el-tag v-if="auth.identity" :type="auth.identity.role === 'admin' ? 'danger' : 'success'">
          {{ auth.identity.role === "admin" ? "管理员" : auth.identity.role === "photographer" ? "摄影师" : auth.identity.role }}
        </el-tag>
        <el-button @click="logout">退出</el-button>
      </div>
    </div>

    <el-menu mode="horizontal" router :default-active="$route.path" style="margin-bottom: 16px">
      <template v-if="auth.identity?.role === 'admin'">
        <el-menu-item :index="withAdminWebBase('/admin/certifications')">认证审核</el-menu-item>
        <el-menu-item :index="withAdminWebBase('/admin/analytics')">埋点分析</el-menu-item>
        <el-menu-item :index="withAdminWebBase('/admin/user-portraits')">用户画像</el-menu-item>
        <el-menu-item :index="withAdminWebBase('/admin/db')">数据库浏览</el-menu-item>
        <el-menu-item :index="withAdminWebBase('/admin/operation-logs')">操作日志</el-menu-item>
        <el-menu-item :index="withAdminWebBase('/seed')">开发 Seed</el-menu-item>
      </template>
      <template v-else-if="auth.identity?.role === 'photographer'">
        <el-menu-item :index="withAdminWebBase('/studio/profile')">我的资料</el-menu-item>
        <el-menu-item :index="withAdminWebBase('/studio/portfolio')">作品管理</el-menu-item>
        <el-menu-item :index="withAdminWebBase('/studio/packages')">套餐管理</el-menu-item>
        <el-menu-item :index="withAdminWebBase('/studio/upload')">上传作品</el-menu-item>
      </template>
    </el-menu>

    <el-alert
      v-if="auth.identity && auth.identity.role !== 'admin'"
      style="margin-bottom: 12px"
      type="info"
      :closable="false"
      title="当前账号不是管理员，已自动切换到摄影师工作台。"
    />

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
