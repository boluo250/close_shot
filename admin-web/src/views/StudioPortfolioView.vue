<template>
  <el-card>
    <template #header>作品管理</template>

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :span="10">
        <el-input v-model="createForm.title" placeholder="标题" />
      </el-col>
      <el-col :span="8">
        <el-input v-model="createForm.tags" placeholder="标签（逗号）" />
      </el-col>
      <el-col :span="6">
        <el-input v-model.number="createForm.sort_order" placeholder="排序" />
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :span="18">
        <el-input v-model="createForm.image_object_key" placeholder="对象键（上传后自动填充）" />
      </el-col>
      <el-col :span="6">
        <el-upload
          :show-file-list="false"
          :auto-upload="true"
          :http-request="onUploadCreate"
          accept="image/*"
        >
          <el-button :loading="uploading">上传图片</el-button>
        </el-upload>
      </el-col>
    </el-row>

    <el-row style="margin-bottom: 16px">
      <el-button type="primary" :loading="creating" @click="create">新增作品</el-button>
      <el-button :loading="loading" style="margin-left: 8px" @click="load">刷新</el-button>
    </el-row>

    <el-table :data="items" v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column label="预览" width="120">
        <template #default="{ row }">
          <img :src="row.image_url" style="width: 96px; height: 64px; object-fit: cover; border-radius: 6px" />
        </template>
      </el-table-column>
      <el-table-column label="标题">
        <template #default="{ row }">
          <el-input v-model="row.title" placeholder="-" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="标签" width="220">
        <template #default="{ row }">
          <el-input v-model="row.tags" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="排序" width="120">
        <template #default="{ row }">
          <el-input v-model.number="row.sort_order" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" :loading="row._saving" @click="saveRow(row)">保存</el-button>
          <el-button size="small" type="danger" :loading="row._deleting" @click="delRow(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top: 10px; color: #888; font-size: 12px">
      上传流程：前端调用 <code>/upload/presign</code>，再用预签名 URL 直传 PUT 到对象存储（MinIO/S3）。
    </div>

    <el-divider content-position="left" style="margin-top: 22px">套餐管理</el-divider>
    <StudioPackagesEditor />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import type { UploadRequestOptions } from "element-plus";

import { api } from "../lib/api";
import { uploadViaPresign } from "../lib/upload";
import StudioPackagesEditor from "../components/StudioPackagesEditor.vue";

type PortfolioItem = {
  id: number;
  title?: string | null;
  image_url: string;
  sort_order: number;
  tags: string;
  _saving?: boolean;
  _deleting?: boolean;
};

const loading = ref(false);
const creating = ref(false);
const uploading = ref(false);

const items = ref<PortfolioItem[]>([]);

const createForm = reactive({
  title: "",
  image_object_key: "",
  sort_order: 0,
  tags: ""
});

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get<{ items: PortfolioItem[] }>("/studio/portfolio");
    items.value = data.items || [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载失败（请用摄影师账号登录）");
  } finally {
    loading.value = false;
  }
}

async function onUploadCreate(opts: UploadRequestOptions) {
  uploading.value = true;
  try {
    const { objectKey } = await uploadViaPresign(opts, { prefix: "portfolio" });
    if (!objectKey) throw new Error("上传结果缺少 object_key");
    createForm.image_object_key = objectKey;
    ElMessage.success("上传成功");
    // ElementPlus 需要手动触发回调
    opts.onSuccess?.({ object_key: objectKey } as any);
  } catch (e: any) {
    ElMessage.error(e?.message || "上传失败");
    opts.onError?.(e);
  } finally {
    uploading.value = false;
  }
}

async function create() {
  if (!createForm.image_object_key) {
    ElMessage.warning("请先填写或上传图片");
    return;
  }
  creating.value = true;
  try {
    const { data } = await api.post<PortfolioItem>("/studio/portfolio", createForm);
    items.value.unshift(data);
    createForm.title = "";
    createForm.image_object_key = "";
    createForm.sort_order = 0;
    createForm.tags = "";
    ElMessage.success("已新增");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "新增失败");
  } finally {
    creating.value = false;
  }
}

async function saveRow(row: PortfolioItem) {
  row._saving = true;
  try {
    await api.put(`/studio/portfolio/${row.id}`, {
      title: row.title,
      tags: row.tags,
      sort_order: row.sort_order
    });
    ElMessage.success("已保存");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    row._saving = false;
  }
}

async function delRow(row: PortfolioItem) {
  row._deleting = true;
  try {
    await api.delete(`/studio/portfolio/${row.id}`);
    items.value = items.value.filter((x) => x.id !== row.id);
    ElMessage.success("已删除");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
  } finally {
    row._deleting = false;
  }
}

onMounted(load);
</script>

