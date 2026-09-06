import { useMutation, useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  type Body_login_login_access_token as AccessToken,
  LoginService,
  type UserPublic,
  type UserRegister,
  UsersService,
} from "@/client"
import { clearAuthSession, queryClient } from "@/lib/queryClient"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

const isLoggedIn = () => {
  return (
    typeof localStorage !== "undefined" &&
    localStorage.getItem("access_token") !== null
  )
}

export const userKeys = {
  current: ["currentUser"] as const,
}

// 当前用户是所有受保护路由和角色导航的单一查询来源。by AI.Coding
export const currentUserQueryOptions = () => ({
  queryKey: userKeys.current,
  queryFn: async (): Promise<UserPublic> =>
    (await UsersService.readUserMe()).data,
  retry: false,
  staleTime: 5 * 60 * 1000,
})

const useAuth = () => {
  const navigate = useNavigate()
  const { showErrorToast } = useCustomToast()

  const currentUserQuery = useQuery({
    ...currentUserQueryOptions(),
    enabled: isLoggedIn(),
  })

  const signUpMutation = useMutation({
    mutationFn: (data: UserRegister) =>
      UsersService.registerUser({ body: data }),
    onSuccess: () => {
      navigate({ to: "/login" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const login = async (data: AccessToken) => {
    // 登录前丢弃可能属于上一个账号的查询结果。by AI.Coding
    queryClient.removeQueries()
    const response = await LoginService.loginAccessToken({
      body: data,
    })
    localStorage.setItem("access_token", response.data.access_token)

    try {
      // 只有当前用户成功加载后，登录 mutation 才算完成。by AI.Coding
      await queryClient.fetchQuery(currentUserQueryOptions())
    } catch (error) {
      clearAuthSession()
      throw error
    }
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const logout = () => {
    clearAuthSession()
    void navigate({ to: "/login", replace: true })
  }

  return {
    signUpMutation,
    loginMutation,
    logout,
    user: currentUserQuery.data,
    isLoading: isLoggedIn() && currentUserQuery.isPending,
    isError: currentUserQuery.isError,
    error: currentUserQuery.error,
  }
}

export { isLoggedIn }
export default useAuth
