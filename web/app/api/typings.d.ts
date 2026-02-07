declare namespace API {
  type AddTaskRequest = {
    /** Taskname */
    taskName: string;
    /** Taskinfo */
    taskInfo?: string | null;
    /** Sourceurl */
    sourceUrl: string;
    /** Sourcepath */
    sourcePath?: string | null;
    /** Targetpath */
    targetPath?: string | null;
    /** File Tasks */
    file_tasks?: FileTaskRequest[];
    /** Type */
    type?: string | null;
  };

  type BaseResponse = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    /** Data */
    data?: any | null;
  };

  type BaseResponseBool_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    /** Data */
    data?: boolean | null;
  };

  type BaseResponseDict_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    /** Data */
    data?: Record<string, any> | null;
  };

  type BaseResponseInt_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    /** Data */
    data?: number | null;
  };

  type BaseResponseListPirateBayTorrent_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    /** Data */
    data?: PirateBayTorrent[] | null;
  };

  type BaseResponseMagnetParseResponse_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: MagnetParseResponse | null;
  };

  type BaseResponseNotificationPage_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: NotificationPage | null;
  };

  type BaseResponseTaskListResponse_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: TaskListResponse | null;
  };

  type BaseResponseTMDBMovie_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: TMDBMovie | null;
  };

  type BaseResponseTMDBMovieListResponse_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: TMDBMovieListResponse | null;
  };

  type BaseResponseTMDBSuggestionResponse_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: TMDBSuggestionResponse | null;
  };

  type BaseResponseTMDBTV_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: TMDBTV | null;
  };

  type BaseResponseTMDBTVListResponse_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: TMDBTVListResponse | null;
  };

  type BaseResponseToken_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: Token | null;
  };

  type BodyLoginForAccessTokenApiV1UsersLoginPost = {
    /** Grant Type */
    grant_type?: string | null;
    /** Username */
    username: string;
    /** Password */
    password: string;
    /** Scope */
    scope?: string;
    /** Client Id */
    client_id?: string | null;
    /** Client Secret */
    client_secret?: string | null;
  };

  type cancelTaskApiV1TasksCancelTaskIdPostParams = {
    task_id: number;
  };

  type deleteNotificationApiV1NotificationsNotificationIdDeleteParams = {
    notification_id: number;
  };

  type DownloadTask = {
    /** Id */
    id: number;
    /** Taskname */
    taskName: string;
    /** Taskinfo */
    taskInfo?: string | null;
    /** Sourceurl */
    sourceUrl?: string | null;
    /** Sourcepath */
    sourcePath?: string | null;
    /** Targetpath */
    targetPath?: string | null;
    taskStatus?: DownloadTaskStatus | null;
    /** Createtime */
    createTime?: string | null;
    /** Updatetime */
    updateTime?: string | null;
    /** Isdelete */
    isDelete: number;
    /** File Tasks */
    file_tasks?: FileTask[];
  };

  type DownloadTaskStatus =
    | "downloading"
    | "moving"
    | "completed"
    | "cancelled"
    | "error";

  type FileTask = {
    /** Id */
    id: number;
    /** Downloadtaskid */
    downloadTaskId: number;
    /** Sourcepath */
    sourcePath: string;
    /** Targetpath */
    targetPath: string;
    /** File Rename */
    file_rename: string;
    file_status: FileTaskStatus;
    /** Errormessage */
    errorMessage?: string | null;
    /** Createtime */
    createTime?: string | null;
    /** Updatetime */
    updateTime?: string | null;
  };

  type FileTaskRequest = {
    /** Sourcepath */
    sourcePath: string;
    /** Targetpath */
    targetPath: string;
    /** File Rename */
    file_rename: string;
  };

  type FileTaskStatus =
    | "pending"
    | "processing"
    | "completed"
    | "failed"
    | "cancelled";

  type getMovieDetailApiV1TmdbMovieMovieIdGetParams = {
    movie_id: number;
  };

  type getNotificationsApiV1NotificationsGetParams = {
    page?: number;
    page_size?: number;
    is_read?: boolean;
  };

  type getSuggestionsApiV1TmdbSuggestionsGetParams = {
    /** 搜索关键词 */
    query: string;
    /** 返回数量限制 */
    limit?: number;
  };

  type getTvDetailApiV1TmdbTvTvIdGetParams = {
    tv_id: number;
  };

  type HTTPValidationError = {
    /** Detail */
    detail?: ValidationError[];
  };

  type listTasksApiV1TasksListGetParams = {
    /** 页码 */
    page?: number;
    /** 每页数量 */
    page_size?: number;
  };

  type MagnetDownloadRequest = {
    /** Magnet Link */
    magnet_link: string;
    /** Save Path */
    save_path?: string | null;
  };

  type MagnetFile = {
    /** Name */
    name: string;
    /** Path */
    path: string;
    /** Size */
    size: number;
  };

  type MagnetParseResponse = {
    /** Files */
    files: MagnetFile[];
  };

  type MagnetRequest = {
    /** Magnet Link */
    magnet_link: string;
  };

  type markReadApiV1NotificationsNotificationIdReadPutParams = {
    notification_id: number;
  };

  type Notification = {
    /** Id */
    id: number;
    /** Title */
    title: string;
    /** Content */
    content?: string | null;
    /** Type */
    type?: string;
    /** Isread */
    isRead: number;
    /** Createtime */
    createTime?: string | null;
    /** Isdelete */
    isDelete: number;
  };

  type NotificationPage = {
    /** Items */
    items: Notification[];
    /** Total */
    total: number;
  };

  type PirateBayTorrent = {
    /** Id */
    id: string;
    /** Name */
    name: string;
    /** Info Hash */
    info_hash: string;
    /** Leechers */
    leechers: string;
    /** Seeders */
    seeders: string;
    /** Size */
    size: string;
    /** Num Files */
    num_files: string;
    /** Username */
    username: string;
    /** Added */
    added: string;
    /** Status */
    status: string;
    /** Category */
    category: string;
    /** Imdb */
    imdb?: string | null;
    /** Magnet */
    magnet?: string | null;
  };

  type searchMovieApiV1TmdbSearchMovieGetParams = {
    /** 搜索关键词 */
    query: string;
    /** 页码 */
    page?: number;
  };

  type searchTorrentsApiV1PiratebaySearchGetParams = {
    /** 搜索关键词 */
    q: string;
  };

  type searchTvApiV1TmdbSearchTvGetParams = {
    /** 搜索关键词 */
    query: string;
    /** 页码 */
    page?: number;
  };

  type TaskListResponse = {
    /** Total */
    total: number;
    /** Items */
    items: DownloadTask[];
  };

  type TMDBMovie = {
    /** Id */
    id: number;
    /** Overview */
    overview?: string | null;
    /** Poster Path */
    poster_path?: string | null;
    /** Backdrop Path */
    backdrop_path?: string | null;
    /** Vote Average */
    vote_average?: number | null;
    /** Original Language */
    original_language?: string | null;
    /** Title */
    title?: string | null;
    /** Original Title */
    original_title?: string | null;
    /** Release Date */
    release_date?: string | null;
  };

  type TMDBMovieListResponse = {
    /** Total */
    total: number;
    /** Items */
    items: TMDBMovie[];
  };

  type TMDBSuggestionResponse = {
    /** Suggestions */
    suggestions: string[];
  };

  type TMDBTV = {
    /** Id */
    id: number;
    /** Overview */
    overview?: string | null;
    /** Poster Path */
    poster_path?: string | null;
    /** Backdrop Path */
    backdrop_path?: string | null;
    /** Vote Average */
    vote_average?: number | null;
    /** Original Language */
    original_language?: string | null;
    /** Name */
    name?: string | null;
    /** Original Name */
    original_name?: string | null;
    /** First Air Date */
    first_air_date?: string | null;
  };

  type TMDBTVListResponse = {
    /** Total */
    total: number;
    /** Items */
    items: TMDBTV[];
  };

  type Token = {
    /** Access Token */
    access_token: string;
    /** Token Type */
    token_type: string;
  };

  type ValidationError = {
    /** Location */
    loc: (string | number)[];
    /** Message */
    msg: string;
    /** Error Type */
    type: string;
  };
}
