<template>
  <el-card>
    <template #header>开发数据生成</template>
    <el-form inline>
      <el-form-item label="lat">
        <el-input v-model.number="form.lat" style="width: 140px" />
      </el-form-item>
      <el-form-item label="lng">
        <el-input v-model.number="form.lng" style="width: 140px" />
      </el-form-item>
      <el-form-item label="city">
        <el-input v-model="form.city" style="width: 140px" />
      </el-form-item>
      <el-form-item label="数量">
        <el-input v-model.number="form.n" style="width: 120px" />
      </el-form-item>
      <el-form-item label="seed">
        <el-input v-model.number="form.seed" style="width: 120px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="onSeed">生成</el-button>
      </el-form-item>
    </el-form>
    <div style="margin-top: 12px; color: #888; font-size: 12px">
      调用后端：<code>POST /dev/seed</code>（仅 dev 环境有效）
    </div>
    <div v-if="result" style="margin-top: 12px">
      <pre>{{ result }}</pre>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";

const loading = ref(false);
const result = ref<string | null>(null);
const form = reactive({ lat: 31.2304, lng: 121.4737, city: "上海", n: 10, seed: 42 });

async function onSeed() {
  loading.value = true;
  try {
    const { data } = await api.post("/dev/seed", null, { params: form });
    result.value = JSON.stringify(data, null, 2);
    ElMessage.success("已生成");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "生成失败");
  } finally {
    loading.value = false;
  }
}
</script>

