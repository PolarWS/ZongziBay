"""
Pydantic 数据模型与 BaseResponse / BusinessException 单元测试
覆盖：ErrorCode、BaseResponse.success/fail、BusinessException 构造、各 Schema 校验
"""
import pytest
from pydantic import ValidationError

from app.schemas.base import BaseResponse, BusinessException, ErrorCode
from app.schemas.auth import Token, TokenData
from app.schemas.bangumi import (
    BangumiCalendarDay,
    BangumiCalendarItem,
    BangumiSubjectDetail,
    BangumiTag,
    BangumiWeekday,
)
from app.schemas.tmdb import (
    TMDBMovie,
    TMDBTV,
    TMDBGenre,
    TMDBMovieDetail,
    TMDBTVDetail,
    TMDBCastMember,
)


# ---------------------------------------------------------------------------
# ErrorCode
# ---------------------------------------------------------------------------

class TestErrorCode:
    """ErrorCode 枚举：code / message 属性"""

    def test_success(self):
        assert ErrorCode.SUCCESS.code == 0
        assert ErrorCode.SUCCESS.message == "ok"

    def test_params_error(self):
        assert ErrorCode.PARAMS_ERROR.code == 40000

    def test_not_login(self):
        assert ErrorCode.NOT_LOGIN_ERROR.code == 40100

    def test_system_error(self):
        assert ErrorCode.SYSTEM_ERROR.code == 50000

    def test_rate_limit(self):
        assert ErrorCode.RATE_LIMIT_ERROR.code == 42900

    @pytest.mark.parametrize("ec", list(ErrorCode))
    def test_all_have_positive_code(self, ec):
        assert ec.code >= 0

    @pytest.mark.parametrize("ec", list(ErrorCode))
    def test_all_have_message(self, ec):
        assert isinstance(ec.message, str)
        assert len(ec.message) > 0


# ---------------------------------------------------------------------------
# BaseResponse
# ---------------------------------------------------------------------------

class TestBaseResponse:
    """BaseResponse.success / fail：统一响应结构"""

    def test_success_default(self):
        r = BaseResponse.success()
        assert r.code == 200
        assert r.message == "success"
        assert r.data is None

    def test_success_with_data(self):
        r = BaseResponse.success(data={"key": "value"})
        assert r.code == 200
        assert r.data == {"key": "value"}

    def test_success_custom_message(self):
        r = BaseResponse.success(message="ok", data="done")
        assert r.message == "ok"

    def test_fail_with_error_code(self):
        r = BaseResponse.fail(code=ErrorCode.PARAMS_ERROR)
        assert r.code == 40000
        assert "参数" in r.message

    def test_fail_with_int_code(self):
        r = BaseResponse.fail(code=500, message="崩溃了")
        assert r.code == 500
        assert r.message == "崩溃了"

    def test_fail_default(self):
        r = BaseResponse.fail()
        assert r.code == 400
        assert r.message == "fail"

    def test_fail_with_data(self):
        r = BaseResponse.fail(code=ErrorCode.PARAMS_ERROR, data=["field1 required"])
        assert r.data == ["field1 required"]

    def test_fail_code_message_override(self):
        r = BaseResponse.fail(code=ErrorCode.PARAMS_ERROR, message="自定义")
        assert r.code == 40000
        assert r.message == "自定义"


# ---------------------------------------------------------------------------
# BusinessException
# ---------------------------------------------------------------------------

class TestBusinessException:
    """BusinessException：业务异常 → BaseResponse 格式"""

    def test_from_error_code(self):
        exc = BusinessException(error=ErrorCode.NOT_LOGIN_ERROR)
        assert exc.code == 40100
        assert "未登录" in exc.message

    def test_custom_message(self):
        exc = BusinessException(error=ErrorCode.PARAMS_ERROR, message="缺少必填字段")
        assert exc.code == 40000
        assert exc.message == "缺少必填字段"

    def test_with_data(self):
        exc = BusinessException(error=ErrorCode.PARAMS_ERROR, data=["field1", "field2"])
        assert exc.data == ["field1", "field2"]

    def test_direct_code(self):
        exc = BusinessException(code=40300, message="禁止访问")
        assert exc.code == 40300
        assert exc.message == "禁止访问"

    def test_default_to_system_error(self):
        exc = BusinessException(message="未知错误")
        assert exc.code == 50000

    def test_is_exception(self):
        exc = BusinessException(code=500, message="test")
        assert isinstance(exc, Exception)

    def test_str_representation(self):
        exc = BusinessException(message="操作失败")
        assert str(exc) == "操作失败"

    def test_with_error_code_and_data(self):
        exc = BusinessException(
            error=ErrorCode.NOT_FOUND_ERROR,
            message="用户不存在",
            data={"id": 999},
        )
        assert exc.code == 40400
        assert exc.data == {"id": 999}

    def test_code_param_takes_precedence(self):
        """当同时传 error 和 code 时，code 优先"""
        exc = BusinessException(
            error=ErrorCode.PARAMS_ERROR,
            code=ErrorCode.NOT_LOGIN_ERROR,
            message="未登录",
        )
        assert exc.code == 40100


# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------

class TestAuthSchemas:
    """Token / TokenData 模型"""

    def test_token_model(self):
        t = Token(access_token="abc.def.ghi", token_type="bearer")
        assert t.access_token == "abc.def.ghi"
        assert t.token_type == "bearer"

    def test_token_data_model(self):
        td = TokenData(username="admin")
        assert td.username == "admin"

    def test_token_data_username_optional(self):
        td = TokenData()
        assert td.username is None


# ---------------------------------------------------------------------------
# Bangumi Schemas
# ---------------------------------------------------------------------------

class TestBangumiSchemas:
    """Bangumi 相关 Pydantic 模型"""

    def test_weekday_model(self):
        wd = BangumiWeekday(id=1, cn="星期一", en="Mon", ja="月曜日")
        assert wd.id == 1
        assert wd.cn == "星期一"

    def test_weekday_all_optional(self):
        wd = BangumiWeekday()
        assert wd.id is None

    def test_calendar_item_model(self):
        item = BangumiCalendarItem(
            id=123,
            name="Test Anime",
            name_cn="测试番剧",
            image="https://example.com/cover.jpg",
            score=8.5,
        )
        assert item.id == 123
        assert item.score == 8.5
        assert item.summary is None

    def test_calendar_day_model(self):
        wd = BangumiWeekday(id=3, cn="星期三")
        items = [BangumiCalendarItem(id=1, name="A"), BangumiCalendarItem(id=2, name="B")]
        day = BangumiCalendarDay(weekday=wd, items=items)
        assert day.weekday.id == 3
        assert len(day.items) == 2

    def test_calendar_day_empty_items(self):
        day = BangumiCalendarDay(weekday=BangumiWeekday(id=7))
        assert day.items == []

    def test_tag_model(self):
        tag = BangumiTag(name="科幻", count=100)
        assert tag.name == "科幻"
        assert tag.count == 100

    def test_subject_detail_model(self):
        tags = [BangumiTag(name="动作"), BangumiTag(name="冒险")]
        detail = BangumiSubjectDetail(
            id=456,
            name="Great Anime",
            summary="An amazing show.",
            score=9.2,
            tags=tags,
            eps=12,
            total_episodes=12,
        )
        assert detail.id == 456
        assert len(detail.tags) == 2
        assert detail.score == 9.2

    def test_subject_detail_url_optional(self):
        detail = BangumiSubjectDetail(id=1, name="Test")
        assert detail.url is None
        assert detail.summary is None


# ---------------------------------------------------------------------------
# TMDB Schemas
# ---------------------------------------------------------------------------

class TestTMDBSchemas:
    """TMDB 相关 Pydantic 模型"""

    def test_movie_model(self):
        m = TMDBMovie(id=550, title="Fight Club", release_date="1999-10-15")
        assert m.id == 550
        assert m.title == "Fight Club"

    def test_tv_model(self):
        tv = TMDBTV(id=1399, name="Game of Thrones")
        assert tv.id == 1399
        assert tv.name == "Game of Thrones"

    def test_genre_model(self):
        g = TMDBGenre(id=28, name="Action")
        assert g.id == 28

    def test_movie_detail_inherits_movie(self):
        detail = TMDBMovieDetail(
            id=100,
            title="Inception",
            tagline="Your mind is the scene of the crime.",
            runtime=148,
            budget=160000000,
        )
        assert detail.id == 100
        assert detail.title == "Inception"
        assert detail.runtime == 148
        assert detail.cast == []

    def test_tv_detail_inherits_tv(self):
        detail = TMDBTVDetail(
            id=200,
            name="Breaking Bad",
            number_of_seasons=5,
            number_of_episodes=62,
        )
        assert detail.id == 200
        assert detail.name == "Breaking Bad"
        assert detail.number_of_seasons == 5

    def test_cast_member_model(self):
        cm = TMDBCastMember(id=123, name="Actor Name", character="Role Name")
        assert cm.name == "Actor Name"
        assert cm.character == "Role Name"

    def test_movie_optional_fields(self):
        m = TMDBMovie(id=1)
        assert m.title is None
        assert m.release_date is None
        assert m.vote_average is None

    def test_tv_optional_fields(self):
        tv = TMDBTV(id=1)
        assert tv.name is None
        assert tv.first_air_date is None
