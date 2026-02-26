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

  type AnimeGardenFansub = {
    /** Id */
    id: number;
    /** Name */
    name: string;
    /** Avatar */
    avatar?: string | null;
  };

  type AnimeGardenPagination = {
    /** Page */
    page: number;
    /** Pagesize */
    pageSize: number;
    /** Complete */
    complete: boolean;
  };

  type AnimeGardenPublisher = {
    /** Id */
    id: number;
    /** Name */
    name: string;
    /** Avatar */
    avatar?: string | null;
  };

  type AnimeGardenResource = {
    /** Id */
    id: number;
    /** Provider */
    provider: string;
    /** Providerid */
    providerId: string;
    /** Title */
    title: string;
    /** Href */
    href: string;
    /** Type */
    type: string;
    /** Magnet */
    magnet: string;
    /** Size */
    size: number;
    /** Createdat */
    createdAt: string;
    /** Fetchedat */
    fetchedAt: string;
    publisher?: AnimeGardenPublisher | null;
    fansub?: AnimeGardenFansub | null;
    /** Subjectid */
    subjectId?: number | null;
  };

  type animeGardenSearchParams = {
    /** 搜索关键词，支持中文/繁体 */
    q: string;
    /** 页码 */
    page?: number;
    /** 每页数量 */
    page_size?: number | null;
    /** 字幕组筛选（名称） */
    fansub?: string | null;
  };

  type AnimeGardenSearchResult = {
    /** Status */
    status: string;
    /** Complete */
    complete: boolean;
    /** Resources */
    resources: AnimeGardenResource[];
    pagination?: AnimeGardenPagination | null;
    /** Filter */
    filter?: Record<string, any> | null;
    /** Timestamp */
    timestamp?: string | null;
  };

  type AnimeGardenTeam = {
    /** Id */
    id: number;
    /** Name */
    name: string;
    /** Provider */
    provider?: string | null;
    /** Providerid */
    providerId?: string | null;
    /** Avatar */
    avatar?: any | null;
  };

  type BaseResponse = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    /** Data */
    data?: any | null;
  };

  /** 射手网(伪) 字幕列表项 */
  type AssrtSubItem = {
    id: number;
    native_name?: string | null;
    revision?: number;
    subtype?: string | null;
    upload_time?: string | null;
    vote_score?: number;
    release_site?: string | null;
    videoname?: string | null;
    lang?: { langlist?: Record<string, boolean>; desc?: string } | null;
  };

  /** 射手网(伪) 详情内单个文件 */
  type AssrtFileListItem = {
    url?: string | null;
    f?: string | null;
    s?: string | null;
  };

  /** 射手网(伪) 字幕详情 */
  type AssrtSubDetail = AssrtSubItem & {
    filename?: string | null;
    size?: number | null;
    url?: string | null;
    view_count?: number | null;
    down_count?: number | null;
    title?: string | null;
    filelist?: AssrtFileListItem[] | null;
    producer?: { uploader?: string; verifier?: string; producer?: string; source?: string } | null;
  };

  /** 射手网(伪) 搜索响应 */
  type AssrtSearchResponse = {
    items: AssrtSubItem[];
    total: number;
    keyword?: string | null;
  };

  type BaseResponseAssrtSearchResponse_ = {
    code?: number;
    message?: string;
    data?: AssrtSearchResponse | null;
  };

  type BaseResponseAssrtSubDetail_ = {
    code?: number;
    message?: string;
    data?: AssrtSubDetail | null;
  };

  type AssrtDownloadResponse = {
    task_id: number;
    task_name: string;
    source_path: string;
    target_path: string;
  };

  type BaseResponseAssrtDownloadResponse_ = {
    code?: number;
    message?: string;
    data?: AssrtDownloadResponse | null;
  };

  type AssrtDownloadBatchResponse = {
    results: AssrtDownloadResponse[];
    message?: string | null;
  };

  type BaseResponseAssrtDownloadBatchResponse_ = {
    code?: number;
    message?: string;
    data?: AssrtDownloadBatchResponse | null;
  };

  type BaseResponseAnimeGardenSearchResult_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: AnimeGardenSearchResult | null;
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

  type BaseResponseListAnimeGardenTeam_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    /** Data */
    data?: AnimeGardenTeam[] | null;
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

  type BaseResponseTMDBEnglishTitleResponse_ = {
    /** Code */
    code?: number;
    /** Message */
    message?: string;
    data?: TMDBEnglishTitleResponse | null;
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
    | "pending_download"
    | "moving"
    | "seeding"
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

  type getMovieEnglishTitleApiV1TmdbMovieMovieIdEnglishTitleGetParams = {
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
    /** 媒体类型: movie / tv，为空则混合搜索 */
    type?: string;
  };

  type getTvDetailApiV1TmdbTvTvIdGetParams = {
    tv_id: number;
  };

  type getTvEnglishTitleApiV1TmdbTvTvIdEnglishTitleGetParams = {
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
    type?: NotificationType;
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

  type NotificationType = "info" | "success" | "warning" | "error";

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

  type serveSpaPathGetParams = {
    path: string;
  };

  type TaskListResponse = {
    /** Total */
    total: number;
    /** Items */
    items: DownloadTask[];
  };

  type TMDBEnglishTitleResponse = {
    /** English Title */
    english_title?: string | null;
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
