from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.user import User
from app.models.team import Team, TeamMember, Invitation, TeamRole, InvitationStatus

router = APIRouter()

# ==================== 依赖函数（必须在模型和路由前定义）====================

def get_current_user(db: Session = Depends(get_db)) -> User:
    """
    获取当前登录用户
    
    在演示环境中，我们默认返回一个演示用户
    """
    # 演示环境下返回默认用户
    user = db.query(User).filter(User.openid == "demo_user_001").first()
    if not user:
        # 创建演示用户
        user = User(
            openid="demo_user_001",
            nickname="演示用户",
            school="上海财经大学",
            lat="31.298886",
            lon="121.492612"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

# ==================== Pydantic 模型 ====================

class TeamCreate(BaseModel):
    """创建团队请求"""
    name: str
    description: Optional[str] = None

class TeamUpdate(BaseModel):
    """更新团队请求"""
    name: Optional[str] = None
    description: Optional[str] = None

class TeamResponse(BaseModel):
    """团队响应"""
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    created_at: datetime
    member_count: int = 0
    is_owner: bool = False
    
    class Config:
        from_attributes = True

class TeamMemberResponse(BaseModel):
    """团队成员响应"""
    id: int
    user_id: int
    role: str
    joined_at: datetime
    user: dict  # 包含用户信息
    
    class Config:
        from_attributes = True

class InvitationCreate(BaseModel):
    """发送邀请请求"""
    team_id: int
    invitee_email: Optional[str] = None  # 被邀请者的邮箱或昵称（演示用）
    invitee_openid: Optional[str] = None  # 被邀请者的 openid

class InvitationResponse(BaseModel):
    """邀请响应"""
    id: int
    team_id: int
    team: dict  # 包含团队信息
    inviter: dict  # 包含邀请者信息
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ==================== 团队管理 API ====================

@router.post("", response_model=TeamResponse)
def create_team(req: TeamCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建团队"""
    team = Team(
        name=req.name,
        description=req.description,
        owner_id=current_user.id
    )
    db.add(team)
    db.flush()
    
    # 将创建者自动添加为owner
    owner_member = TeamMember(
        team_id=team.id,
        user_id=current_user.id,
        role=TeamRole.OWNER
    )
    db.add(owner_member)
    db.commit()
    db.refresh(team)
    
    return {
        **team.__dict__,
        "member_count": 1,
        "is_owner": True
    }

@router.get("", response_model=List[TeamResponse])
def list_teams(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户所属的所有团队"""
    # 获取用户创建的团队
    owned_teams = db.query(Team).filter(Team.owner_id == current_user.id).all()
    
    # 获取用户加入的团队
    member_teams = db.query(Team).join(TeamMember).filter(
        TeamMember.user_id == current_user.id,
        Team.owner_id != current_user.id
    ).all()
    
    all_teams = owned_teams + member_teams
    
    return [
        {
            **team.__dict__,
            "member_count": len(team.members),
            "is_owner": team.owner_id == current_user.id
        }
        for team in all_teams
    ]

@router.get("/{team_id}", response_model=TeamResponse)
def get_team(team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取团队详情"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 验证用户是否有权限查看
    is_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()
    
    if not is_member and team.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此团队")
    
    return {
        **team.__dict__,
        "member_count": len(team.members),
        "is_owner": team.owner_id == current_user.id
    }

@router.put("/{team_id}", response_model=TeamResponse)
def update_team(team_id: int, req: TeamUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新团队信息（仅owner可操作）"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    if team.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="仅团队创建者可修改")
    
    if req.name:
        team.name = req.name
    if req.description is not None:
        team.description = req.description
    
    team.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(team)
    
    return {
        **team.__dict__,
        "member_count": len(team.members),
        "is_owner": True
    }

@router.delete("/{team_id}")
def delete_team(team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除团队（仅owner可操作）"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    if team.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="仅团队创建者可删除")
    
    db.delete(team)
    db.commit()
    
    return {"message": "团队已删除"}

@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
def get_team_members(team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取团队成员列表"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 验证用户是否有权限
    is_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()
    
    if not is_member and team.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限查看")
    
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role.value,
            "joined_at": m.joined_at,
            "user": {
                "id": m.user.id,
                "openid": m.user.openid,
                "nickname": m.user.nickname or "未命名",
                "school": m.user.school
            }
        }
        for m in members
    ]

@router.delete("/{team_id}/members/{member_id}")
def remove_member(team_id: int, member_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """移除团队成员（仅owner或成员本人可操作）"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.id == member_id
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 权限检查：owner或本人
    if team.owner_id != current_user.id and member.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限移除此成员")
    
    # owner不能被移除
    if member.role == TeamRole.OWNER:
        raise HTTPException(status_code=400, detail="无法移除团队创建者")
    
    db.delete(member)
    db.commit()
    
    return {"message": "成员已移除"}

# ==================== 邀请管理 API ====================

@router.post("/invitations", response_model=InvitationResponse)
def send_invitation(req: InvitationCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发送团队邀请"""
    team = db.query(Team).filter(Team.id == req.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 验证发起人是否是团队成员
    is_member = db.query(TeamMember).filter(
        TeamMember.team_id == req.team_id,
        TeamMember.user_id == current_user.id
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="只有团队成员可发送邀请")
    
    # 查询被邀请者
    invitee = None
    search_openid = None
    
    if req.invitee_openid:
        search_openid = req.invitee_openid
        invitee = db.query(User).filter(User.openid == search_openid).first()
    elif req.invitee_email:
        # 为了演示，允许通过邮箱搜索（实际应用中应该有邮箱字段）
        # 这里简单地生成一个 openid
        search_openid = f"user_{req.invitee_email.replace('@', '_')}"
        invitee = db.query(User).filter(User.openid == search_openid).first()
        if not invitee:
            # 创建新用户（演示）
            invitee = User(
                openid=search_openid,
                nickname=req.invitee_email.split('@')[0]
            )
            db.add(invitee)
            db.flush()
    else:
        raise HTTPException(status_code=400, detail="需要提供 invitee_openid 或 invitee_email")
    
    # 检查被邀请者是否已在团队中
    if invitee:
        is_member = db.query(TeamMember).filter(
            TeamMember.team_id == req.team_id,
            TeamMember.user_id == invitee.id
        ).first()
        if is_member:
            raise HTTPException(status_code=400, detail="该用户已是团队成员")
    
    # 检查是否已有待处理的邀请
    existing = db.query(Invitation).filter(
        Invitation.team_id == req.team_id,
        Invitation.invitee_openid == search_openid,
        Invitation.status == InvitationStatus.PENDING
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已有待处理的邀请")
    
    # 创建邀请
    invitation = Invitation(
        team_id=req.team_id,
        inviter_id=current_user.id,
        invitee_id=invitee.id if invitee else None,
        invitee_openid=search_openid,
        status=InvitationStatus.PENDING
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    
    return {
        "id": invitation.id,
        "team_id": invitation.team_id,
        "team": {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "member_count": len(team.members)
        },
        "inviter": {
            "id": current_user.id,
            "openid": current_user.openid,
            "nickname": current_user.nickname or "用户"
        },
        "status": invitation.status.value,
        "created_at": invitation.created_at
    }

@router.get("/invitations", response_model=List[InvitationResponse])
def get_invitations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户的邀请列表"""
    invitations = db.query(Invitation).filter(
        (Invitation.invitee_id == current_user.id) | (Invitation.invitee_openid == current_user.openid),
        Invitation.status == InvitationStatus.PENDING
    ).all()
    
    return [
        {
            "id": inv.id,
            "team_id": inv.team_id,
            "team": {
                "id": inv.team.id,
                "name": inv.team.name,
                "description": inv.team.description,
                "member_count": len(inv.team.members)
            },
            "inviter": {
                "id": inv.inviter.id,
                "openid": inv.inviter.openid,
                "nickname": inv.inviter.nickname or "用户"
            },
            "status": inv.status.value,
            "created_at": inv.created_at
        }
        for inv in invitations
    ]

@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(invitation_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """接受邀请"""
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在")
    
    # 验证邀请是否是发给当前用户的
    if invitation.invitee_id != current_user.id and invitation.invitee_openid != current_user.openid:
        raise HTTPException(status_code=403, detail="无权限操作此邀请")
    
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="邀请已处理")
    
    # 检查邀请是否过期（7天）
    if datetime.utcnow() - invitation.created_at > timedelta(days=7):
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=400, detail="邀请已过期")
    
    # 添加为团队成员
    member = TeamMember(
        team_id=invitation.team_id,
        user_id=current_user.id,
        role=TeamRole.MEMBER
    )
    db.add(member)
    
    # 更新邀请状态
    invitation.status = InvitationStatus.ACCEPTED
    invitation.invitee_id = current_user.id
    invitation.responded_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "已加入团队"}

@router.post("/invitations/{invitation_id}/reject")
def reject_invitation(invitation_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """拒绝邀请"""
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在")
    
    # 验证邀请是否是发给当前用户的
    if invitation.invitee_id != current_user.id and invitation.invitee_openid != current_user.openid:
        raise HTTPException(status_code=403, detail="无权限操作此邀请")
    
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="邀请已处理")
    
    # 更新邀请状态
    invitation.status = InvitationStatus.REJECTED
    invitation.responded_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "已拒绝邀请"}

# ==================== 邀请链接 API ====================

@router.post("/generate_invite_link")
def generate_invite_link(req: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """生成团队邀请链接"""
    # 获取团队ID
    team_id = req.get("teamId")
    if not team_id:
        raise HTTPException(status_code=400, detail="缺少团队ID")
    
    # 检查团队是否存在
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 检查用户是否是团队成员
    team_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()
    
    if not team_member:
        raise HTTPException(status_code=403, detail="只有团队成员可生成邀请链接")
    
    # 生成邀请码
    import uuid
    invite_code = str(uuid.uuid4()).replace("-", "")[:16]
    
    # 创建邀请记录
    invitation = Invitation(
        team_id=team_id,
        inviter_id=current_user.id,
        status=InvitationStatus.PENDING,
        invite_code=invite_code
    )
    
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    
    # 生成邀请链接
    base_url = "https://your-mini-program-url.com"
    invite_link = f"{base_url}/pages/team/invitations?teamId={team_id}&inviteCode={invite_code}"
    
    return {
        "link": invite_link,
        "inviteCode": invite_code,
        "teamId": team_id
    }

@router.post("/accept_invite")
def accept_invite(req: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """通过邀请码接受团队邀请"""
    team_id = req.get("teamId")
    invite_code = req.get("inviteCode")
    
    if not team_id or not invite_code:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    
    # 查找邀请信息
    invitation = db.query(Invitation).filter(
        Invitation.team_id == team_id,
        Invitation.invite_code == invite_code,
        Invitation.status == InvitationStatus.PENDING
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在或已失效")
    
    # 验证团队是否存在
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 检查用户是否已经是团队成员
    is_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()
    
    if is_member:
        raise HTTPException(status_code=400, detail="您已经是团队成员")
    
    # 将用户添加到团队
    team_member = TeamMember(
        team_id=team_id,
        user_id=current_user.id,
        role=TeamRole.MEMBER
    )
    db.add(team_member)
    
    # 更新邀请状态
    invitation.status = InvitationStatus.ACCEPTED
    invitation.invitee_id = current_user.id
    invitation.invitee_openid = current_user.openid
    invitation.responded_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "成功加入团队"}
