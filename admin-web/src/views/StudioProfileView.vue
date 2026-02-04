<template>
  <el-card>
    <template #header>摄影师资料</template>

    <el-form label-width="120px" :model="form" style="max-width: 720px">
      <el-form-item label="城市">
        <el-input v-model="form.city" placeholder="如：上海" />
      </el-form-item>
      <el-form-item label="标签（逗号）">
        <el-input v-model="form.tags" placeholder="人像,旅拍,婚纱" />
      </el-form-item>
      <el-form-item label="简介">
        <el-input v-model="form.bio" type="textarea" :rows="4" />
      </el-form-item>
      <el-form-item label="在线状态">
        <el-switch v-model="form.is_online" />
      </el-form-item>
      <el-form-item label="定位 lat/lng">
        <el-row :gutter="12" style="width: 100%">
          <el-col :span="12"><el-input v-model.number="form.lat" placeholder="lat" /></el-col>
          <el-col :span="12"><el-input v-model.number="form.lng" placeholder="lng" /></el-col>
        </el-row>
      </el-form-item>
      <el-form-item label="接单半径（米）">
        <el-input v-model.number="form.service_radius_m" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";

type Photographer = {
  id: number;
  city?: string | null;
  tags: string;
  bio?: string | null;
  is_online: boolean;
  lat?: number | null;
  lng?: number | null;
  service_radius_m: number;
};

const loading = ref(false);
const saving = ref(false);
const form = reactive<Photographer>({
  id: 0,
  city: "",
  tags: "",
  bio: "",
  is_online: false,
  lat: null,
  lng: null,
  service_radius_m: 5000
});

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get<{ photographer: Photographer }>("/studio/me");
    Object.assign(form, data.photographer);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载失败（请用摄影师账号登录）");
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const payload = {
      city: form.city,
      tags: form.tags,
      bio: form.bio,
      is_online: form.is_online,
      lat: form.lat,
      lng: form.lng,
      service_radius_m: form.service_radius_m
    };
    const { data } = await api.put<{ photographer: Photographer }>("/studio/me", payload);
    Object.assign(form, data.photographer);
    ElMessage.success("已保存");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

