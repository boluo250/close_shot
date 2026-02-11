<template>
  <div class="cs-page">
    <div class="cs-header">
      <div><b>Close Shot 后台（MVP）</b></div>
      <div><el-button @click="logout">退出</el-button></div>
    </div>

    <el-menu mode="horizontal" router :default-active="$route.path" style="margin-bottom: 16px">
      <el-menu-item index="/studio/profile">资料</el-menu-item>
      <el-menu-item index="/studio/portfolio">作品</el-menu-item>
      <el-menu-item index="/studio/packages">套餐</el-menu-item>
      <el-menu-item index="/admin/certifications">认证审核</el-menu-item>
      <el-menu-item index="/seed">开发 Seed</el-menu-item>
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

const auth = useAuthStore();
function logout() {
  auth.logout();
  router.push("/login");
}
</script>

