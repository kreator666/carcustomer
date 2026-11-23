import axios from 'axios';
import { ElMessage } from 'element-plus';

// 统一封装：baseURL=/api，解包 {ok,data}，错误统一 ElMessage 提示
const http = axios.create({ baseURL: '/api', timeout: 30000 });

http.interceptors.response.use(
  (resp) => {
    // 后端统一返回 {ok, data|error}
    if (resp.data && typeof resp.data === 'object' && 'ok' in resp.data) {
      if (resp.data.ok) return resp.data.data;
      ElMessage.error(resp.data.error || '请求失败');
      return Promise.reject(new Error(resp.data.error || '请求失败'));
    }
    return resp.data;
  },
  (err) => {
    const msg =
      (err.response && err.response.data && err.response.data.error) ||
      err.message ||
      '网络错误';
    ElMessage.error(String(msg));
    return Promise.reject(err);
  }
);

export default http;
