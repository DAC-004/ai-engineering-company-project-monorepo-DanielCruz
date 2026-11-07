"""Shared rank hierarchy must coexist with Task 4 and Task 5 named staff."""
import pytest
from agents.supplier_contracts.actor import ActorIdentity as ContractActor,ActorRejected,named_approver_from_actor
from agents.financial_close.identity import ActorIdentity as CloseActor,CLAIRE,trusted_named_person,TOM_EMAIL,named_tom_from_actor

def test_authorized_claire_supervisor_can_approve_contracts_and_receive_close_notices():
    fields=dict(user_id='fictional-claire',role='supervisor',department_id='compliance',email='claire.compliance@healthcore.example',can_approve=True)
    assert named_approver_from_actor(ContractActor(**fields))==CLAIRE
    assert trusted_named_person(CloseActor(**fields))==CLAIRE

def test_claire_employee_still_cannot_approve_contracts():
    fields=dict(user_id='fictional-claire',role='employee',department_id='compliance',email='claire.compliance@healthcore.example',can_approve=False)
    with pytest.raises(ActorRejected):named_approver_from_actor(ContractActor(**fields))
    assert trusted_named_person(CloseActor(**fields))==CLAIRE

def test_named_tom_review_remains_exact_supervisor_identity():
    fields=dict(user_id='fictional-tom',role='admin',department_id='revenue_cycle',email=TOM_EMAIL,can_approve=True,is_admin=True)
    with pytest.raises(ValueError):named_tom_from_actor(CloseActor(**fields))

@pytest.mark.parametrize('changes',[{'department_id':'clinical_operations'},{'email':'other@healthcore.example'},{'is_active':False},{'role':'unknown'}])
def test_promoted_claire_does_not_bypass_identity_department_or_active_state(changes):
    fields=dict(user_id='fictional-claire',role='supervisor',department_id='compliance',email='claire.compliance@healthcore.example',can_approve=True)
    fields.update(changes)
    assert trusted_named_person(CloseActor(**fields)) is None
