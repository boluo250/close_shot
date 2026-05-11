<template>
  <div style="max-width: 360px; margin: 100px auto">
    <el-card>
      <template #header>后台登录</template>
      <el-form :model="form" @submit.prevent>
        <el-form-item label="用户名">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" autocomplete="current-password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onLogin">登录</el-button>
        </el-form-item>
      </el-form>
      <div v-if="isDev" style="color: #888; font-size: 12px">
        开发环境可用后端接口创建管理员：<code>/auth/dev/create-admin</code>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";
import { ADMIN_HOME_PATH } from "../lib/adminSecurity";
import { useAuthStore } from "../stores/auth";
import { router } from "../router";

const auth = useAuthStore();
const isDev = import.meta.env.DEV;
const loading = ref(false);
const form = reactive({ username: "", password: "" });

async function onLogin() {
  loading.value = true;
  try {
    const { data } = await api.post("/auth/login", form);
    auth.setToken(data.access_token);
    await router.push(ADMIN_HOME_PATH);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>
